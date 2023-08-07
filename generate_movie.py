import sys
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, CompositeVideoClip, VideoClip
from moviepy.video.VideoClip import ImageClip
import ffmpeg
from tqdm import tqdm
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.editor import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from pydub import AudioSegment
import requests
import io
import re
import MeCab
import unidic
import pandas as pd
import alkana

# Helper function: Convert alphabet to Katakana
# https://qiita.com/kunishou/items/814e837cf504ce287a13
def alpha_to_kana(text):
	# Check if string is alphabetic
	alphaReg = re.compile(r'^[a-zA-Z]+$')
	def isalpha(s):
		return alphaReg.match(s) is not None

	sample_txt = text

	wakati = MeCab.Tagger('-Owakati')
	wakati_result = wakati.parse(sample_txt)

	df = pd.DataFrame(wakati_result.split(" "),columns=["word"])
	df = df[df["word"].str.isalpha() == True]
	df["english_word"] = df["word"].apply(isalpha)
	df = df[df["english_word"] == True]
	df["katakana"] = df["word"].apply(alkana.get_kana)

	dict_rep = dict(zip(df["word"], df["katakana"]))

	for word, read in dict_rep.items():
		sample_txt = sample_txt.replace(word, read or "")
	return sample_txt

TTF_FONTFILE='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

def draw_trajectory(frame, current_time, trajectory, clear_events):
	img = Image.fromarray(frame)
	draw = ImageDraw.Draw(img)

	# Clear all existing trajectories if the current time matches any of the clear_events
	already_clipped = [clear_time for clear_time in clear_events if clear_time < current_time * 1000]
	last_clipped = max(already_clipped) if len(already_clipped) > 0 else -1

	# Draw the trajectory
	for i, item in enumerate(trajectory):
		start_time, draw_time, x, y = item
		prev_start_time, prev_time, prev_x, prev_y = trajectory[i - 1] if i > 0 else [-1, 0, 0, 0]
		x = x * img.width + img.width / 2
		y = y * img.width + img.height / 2
		prev_x = prev_x * img.width + img.width / 2
		prev_y = prev_y * img.width + img.height / 2
		if prev_start_time != start_time:
			continue
		if last_clipped < draw_time and draw_time <= current_time * 1000:
			draw.line((prev_x, prev_y, x, y), fill="red", width=3)

	return np.array(img)

def compose_video_with_trajectory(video, trajectory, clear_events):
	def process_frame(get_frame, t):
		frame = get_frame(t)
		return draw_trajectory(frame, t, trajectory, clear_events)

	new_video = video.fl(lambda gf, t: process_frame(gf, t), apply_to=['mask', 'video'])
	return new_video
	
def read_comments(comments_filename):
	trajectory = []
	clear_events = []
	with open(comments_filename, 'r') as f:
		comments = json.load(f)
		if isinstance(comments, dict):
			trajectory = comments["trajectory"]
			clear_events = comments["clear"]
			comments = comments["comments"]
	return comments, trajectory, clear_events

def apply_speed_change(clip, comment_text):
	if re.match(r'^>+(\n)*$', comment_text):
		speed_multiplier = len(comment_text.strip())
		return clip.speedx(speed_multiplier)
	elif re.match(r'^<+(\n)*$', comment_text):
		speed_divisor = len(comment_text.strip())
		return clip.speedx(1 / speed_divisor)
	else:
		return clip

def parse_comment(comment, use_literal=True):
	def replacer(match):
		literal, pronoun = match.groups()
		return literal if use_literal else pronoun

	return re.sub(r"\{(.+?)\|(.+?)\}", replacer, comment)
	
def process_video_speed_and_offsets(video, comments):
	# First pass: create the processed clips and calculate the adjustments
	processed_clips = []
	current_speed = 1
	current_time = 0
	bracket_level = 0
	cumulative_adjustment = 0
	adjustments = []

	for comment in comments:
		start_ms, text = comment
		start_s = start_ms / 1000.0

		if text == "[":
			bracket_level += 1
			if bracket_level == 2:  # Nested bracket detected, reset bracket level
				bracket_level = 0
			adjustments.append(cumulative_adjustment)
			continue
		elif text == "]":
			bracket_level = max(0, bracket_level - 1)
			adjustments.append(cumulative_adjustment)
			continue

		if bracket_level > 0:  # Inside a bracket, skip this comment
			adjustments.append(cumulative_adjustment)
			continue

		new_speed = apply_speed_multiplier(text, current_speed)
		if new_speed != current_speed:  # Speed change detected
			if current_time != start_s:
				clip = video.subclip(current_time, start_s).speedx(current_speed)
				print("%f-%f (x%f)"%(current_time, start_s, current_speed))
				processed_clips.append(clip)
				clip_duration = start_s - current_time
				adjustment = (clip_duration / current_speed - clip_duration) * 1000
				cumulative_adjustment += adjustment
			current_speed = new_speed
			current_time = start_s
		clip_duration = start_s - current_time
		adjustment = (clip_duration / current_speed - clip_duration) * 1000
		adjustments.append(cumulative_adjustment + adjustment)

	# Add the remaining part of the video with the last speed change applied
	processed_clips.append(video.subclip(current_time).speedx(current_speed))
	print("%f- (x%f)"%(current_time, current_speed))

	# Second pass: apply the adjustments to the comments
	adjusted_comments = []
	for i, comment in enumerate(comments):
		start_ms, text = comment
		adjustment = adjustments[i]
		adjusted_comments.append([start_ms + adjustment, text])
		print("%f-->%f: %s"%(start_ms / 1000, (start_ms + adjustment)/1000, text))

	return concatenate_videoclips(processed_clips), adjusted_comments



def apply_speed_multiplier(text, current_speed):
	if re.match(r'^>+(\n)*$', text):
		return len(text.strip())
	elif re.match(r'^<+(\n)*$', text):
		return 1 / len(text.strip())
	else:
		return current_speed

def create_text_image(text, width, height):
	image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
	font = ImageFont.truetype(TTF_FONTFILE, 50)
	draw = ImageDraw.Draw(image)
	max_width = width
	wrapped_text = ""

	for line in text.split('\n'):
		line_width = draw.textbbox((0, 0), line, font=font)[2]
		if line_width <= max_width:
			wrapped_text += line + "\n"
		else:
			delimiter = ' '
			words = line.split(delimiter)
			if len(words) == 1:
				tagger = MeCab.Tagger("-Owakati")        
				words = tagger.parse(line).split(delimiter)
				delimiter = ''
			current_line = ""
			for word in words:
				word_width = draw.textbbox((0, 0), current_line + word + delimiter, font=font)[2]
				if word_width <= max_width:
					current_line += word + delimiter
				else:
					wrapped_text += current_line + '\n'
					current_line = word + delimiter
			wrapped_text += current_line + '\n'

	lines = wrapped_text.split('\n')
	print(lines)

	total_text_height = sum([draw.textbbox((0, 0), line, font=font)[3] for line in lines])
	y_text = height - total_text_height

	for line in lines:
		text_size = draw.textbbox((0, 0), line, font=font)
		text_pos = ((width - text_size[2]) // 2, y_text)
		x, y = text_pos
		black = (0, 0, 0, 255)  # Black edge
		for offset in range(-3, 4):
			draw.text((x+offset, y), line, font=font, fill=black)
			draw.text((x-offset, y), line, font=font, fill=black)
			draw.text((x, y+offset), line, font=font, fill=black)
			draw.text((x, y-offset), line, font=font, fill=black)
			draw.text((x+offset, y+offset), line, font=font, fill=black)
			draw.text((x+offset, y-offset), line, font=font, fill=black)
			draw.text((x-offset, y+offset), line, font=font, fill=black)
			draw.text((x-offset, y-offset), line, font=font, fill=black)

		white = (255, 255, 255, 255)  # White text
		draw.text(text_pos, line, font=font, fill=white)
		y_text += text_size[3]

	image = cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2BGRA)
	return image

def overlay_text_comments(video_filename, comments):
	if isinstance(video_filename, str):
		video = VideoFileClip(video_filename, audio=False)  # Remove audio
	elif isinstance(video_filename, VideoClip):
		video = video_filename
	else:
		return None
	video_size = video.size
	clips = [video]

	for i in range(len(comments)):
		start_ms, text, duration_ms = comments[i]
		start_sec = start_ms / 1000.0  # Convert milliseconds to seconds
		literal_text = parse_comment(text)  # Use the literal part for overlay text

		if i < len(comments) - 1:
			next_start_ms, *_ = comments[i + 1]
			duration = min((next_start_ms - start_ms) / 1000.0, duration_ms / 1000.0)
		else:
			duration = 10

		print("%d: duration=%f sec"%(i, duration))
		text_image = create_text_image(literal_text, video_size[0], video_size[1])
		txt_clip = (ImageClip(text_image, duration=duration).set_start(start_sec))
		clips.append(txt_clip)

	return clips

def add_audio_comments(video_filename, audio_filename, output_filename):
	input_video = ffmpeg.input(video_filename)
	input_audio = ffmpeg.input(audio_filename)
	ffmpeg.concat(input_video, input_audio, v=1, a=1).output(output_filename).run(overwrite_output=True)

def preview_video(comments, video_filename, audio_comments_filename):
	# Overlay text comments on video
	video_clips = overlay_text_comments(video_filename, comments)
	final_video = CompositeVideoClip(video_clips)

	# Generate audio comments
	audio = AudioFileClip(audio_comments_filename)

	# Set the duration of the audio to match the video
#    audio = audio.set_duration(final_video.duration)

	# Set audio to the video
	final_video = final_video.set_audio(audio)

	# Preview the video
	final_video.preview()

def generate_video(comments, video_filename, audio_comments_filename, final_filename):
	# Overlay text comments on video
	video_clips = overlay_text_comments(video_filename, comments)
	final_video = CompositeVideoClip(video_clips)

	# Generate audio comments
	audio = AudioFileClip(audio_comments_filename)

	# Set the duration of the audio to match the video
#    audio = audio.set_duration(final_video.duration)

	# Set audio to the video
	final_video = final_video.set_audio(audio)

	# Preview the video
	final_video.write_videofile(final_filename, codec='libx264')

	
def generate_wav(filename, comments, audioSpeedScale, speaker = 0):
	# Create an empty audio track of silence for mixdown
	mixdown_audio = AudioSegment.silent(duration=0)

	# Iterate over the sorted comments
	for comment in tqdm(sorted(comments, key=lambda x: x[0])):
		text = comment[1]
		text = alpha_to_kana(text)
		pronoun_text = parse_comment(text, use_literal=False) # Use the pronoun part for play_speech
		res1 = requests.post("http://localhost:50021/audio_query", params={"text": pronoun_text if pronoun_text else text, "speaker": speaker})
		data = res1.json()
		if "speedScale" in data:
			data["speedScale"] *= audioSpeedScale
		wav_res = requests.post("http://localhost:50021/synthesis", params={"speaker": speaker}, json=data)
		wav_data = wav_res.content
		
		# Load the wav_data into an AudioSegment
		audio_segment = AudioSegment.from_wav(io.BytesIO(wav_data))
		
		# If the audio_segment is shorter than the comment[0] offset, pad it with silence
		audio_duration_ms = len(audio_segment)
		silence_duration_ms = max(0, comment[0] - len(mixdown_audio))
		silence = AudioSegment.silent(duration=silence_duration_ms)
		comment.append(audio_duration_ms)
		
		# Append silence and audio_segment to mixdown_audio
		mixdown_audio += silence
		mixdown_audio += audio_segment

	# Export the mixdown_audio to a .wav file
	output_filename = filename + ".comments.wav"
	mixdown_audio.export(output_filename, format="wav")
	return output_filename

def main():
	video_filename = sys.argv[1]
	comments_filename = video_filename + ".comments.json"
	comments, trajectory, clear_events = read_comments(comments_filename)
#    comments = comments[0:3]
	audioSpeedScale = float(sys.argv[3]) if len(sys.argv) > 3 and float(sys.argv[3]) else 1.0

	if len(sys.argv) > 2 and sys.argv[2] == '--audio':
		text_overlay_video_filename = video_filename[:-4] + "_text_overlay.mp4"        
		audio_comments_filename = video_filename + ".comments.wav"
		# Combine video with overlay text and audio comments
		output_filename = video_filename[:-4] + "_final.mp4"
		add_audio_comments(text_overlay_video_filename, audio_comments_filename, output_filename)

	else:
		video = VideoFileClip(video_filename, audio=False)
		video_with_trajectory = compose_video_with_trajectory(video, trajectory, clear_events)

		processed_video, updated_comments = process_video_speed_and_offsets(video_with_trajectory, comments)

		if len(sys.argv) > 2 and sys.argv[2] == '--preview':
			audio_comments_filename = generate_wav(video_filename, updated_comments, audioSpeedScale)
			preview_video(updated_comments, processed_video, audio_comments_filename)
		else:
			audio_comments_filename = generate_wav(video_filename, updated_comments, audioSpeedScale)
			output_filename = video_filename[:-4] + "_final.mp4"
			generate_video(updated_comments, processed_video, audio_comments_filename, output_filename)

if __name__ == "__main__":
	main()