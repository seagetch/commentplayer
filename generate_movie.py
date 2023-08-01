import sys
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, CompositeVideoClip
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

def read_comments(comments_filename):
    with open(comments_filename, 'r') as f:
        comments = json.load(f)
    return comments

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
    video = VideoFileClip(video_filename, audio=False)  # Remove audio
    video_size = video.size
    clips = [video]

    for i in range(len(comments)):
        start_ms, text, duration_ms = comments[i]
        start_sec = start_ms / 1000.0  # Convert milliseconds to seconds

        if i < len(comments) - 1:
            next_start_ms, *_ = comments[i + 1]
            duration = min((next_start_ms - start_ms) / 1000.0, duration_ms / 1000.0)
        else:
            duration = 10

        text_image = create_text_image(text, video_size[0], video_size[1])
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
        res1 = requests.post("http://localhost:50021/audio_query", params={"text": text, "speaker": speaker})
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
    video_filename = sys.argv[1]  # Get source video filename from command line arguments

    # Read comments data
    comments_filename = video_filename + ".comments.json"
    comments = read_comments(comments_filename)
    audioSpeedScale = float(sys.argv[3]) if len(sys.argv) > 3 and float(sys.argv[3]) else 1.0

    if len(sys.argv) > 2 and sys.argv[2] == '--preview':
        # Generate audio comments
        audio_comments_filename = generate_wav(video_filename, comments, audioSpeedScale)

        # Show a preview instead of generating final video
        preview_video(comments, video_filename, audio_comments_filename)
    elif len(sys.argv) > 2 and sys.argv[2] == '--audio':
        text_overlay_video_filename = video_filename[:-4] + "_text_overlay.mp4"        
        audio_comments_filename = video_filename + ".comments.wav"
        # Combine video with overlay text and audio comments
        output_filename = video_filename[:-4] + "_final.mp4"
        add_audio_comments(text_overlay_video_filename, audio_comments_filename, output_filename)
    else:
        # Generate audio comments
        audio_comments_filename = generate_wav(video_filename, comments, audioSpeedScale)
        output_filename = video_filename[:-4] + "_final.mp4"
        generate_video(comments, video_filename, audio_comments_filename, output_filename)

        # Overlay text comments on video
#        video_clips = overlay_text_comments(video_filename, comments)
#        final_video = CompositeVideoClip(video_clips)
#        text_overlay_video_filename = video_filename[:-4] + "_text_overlay.mp4"
#        final_video.write_videofile(text_overlay_video_filename, codec='libx264')

        # Combine video with overlay text and audio comments
#        add_audio_comments(text_overlay_video_filename, audio_comments_filename, output_filename)

if __name__ == "__main__":
    main()

