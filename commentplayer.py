import sys
from PySide2.QtCore import Qt, QUrl, QTimer, Signal, QIODevice, QByteArray
from PySide2.QtGui import QTextCursor, QCloseEvent, QPixmap, QKeyEvent,  QInputMethodEvent
from PySide2.QtMultimedia import QMediaContent, QMediaPlayer
from PySide2.QtMultimediaWidgets import QVideoWidget
from PySide2.QtWidgets import (QApplication, QSlider, QVBoxLayout, QWidget,
                               QTextEdit, QTableWidget, QTableWidgetItem, QHBoxLayout, QLabel, QPushButton,
                               QToolButton, QAbstractItemView, QLineEdit)
from PySide2.QtWidgets import QSizePolicy

import requests, threading
import qtawesome as qta
import json
import tempfile

import MeCab
import unidic
import pandas as pd
import alkana
import re
import os
import tqdm
from pydub import AudioSegment
import io, wave

# Global variable for the hostname of the VOICEVOX server
VOICEVOX_SERVER = "http://localhost:50021"

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


class IMETextEdit(QTextEdit):
    editingStarted = Signal()

    def inputMethodEvent(self, event: QInputMethodEvent):
        if event.commitString() or event.preeditString():
            self.editingStarted.emit()
        super().inputMethodEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() not in {Qt.Key_Return, Qt.Key_Enter}:
            self.editingStarted.emit()
        super().keyPressEvent(event)

class VideoPlayer(QWidget):
    def __init__(self, filename, parent=None, playbackRate = 1.0, audioSpeedScale = 1.0):
        super(VideoPlayer, self).__init__(parent)

        self.filename = filename
        self.playbackRate = playbackRate
        self.playbackScale = 1.0

        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.voicePlayer = QMediaPlayer()
        self.videoWidget = QVideoWidget()
        self.slider = QSlider(Qt.Horizontal)
        self.playButton  = QToolButton()
        self.commentEdit = IMETextEdit()
        self.commentsTable = QTableWidget(0, 3)
        self.loadingLabel = QLabel()
        self.positionLabel = QLabel("00:00:00")
        self.editPositionLabel = QLabel()
        self.saveButton = QPushButton("Save")
        self.loadButton = QPushButton("Load")
        self.generateWavButton = QPushButton("export WAV")
        
        self.commentOverlay = QLabel()
        self.commentOverlay.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        videoLayout = QVBoxLayout()
        videoLayout.addWidget(self.videoWidget)
        videoLayout.addWidget(self.commentOverlay)
        videoMenuLayout = QHBoxLayout()
        videoLayout.addLayout(videoMenuLayout)
        videoMenuLayout.addWidget(self.slider)
        videoMenuLayout.addWidget(self.positionLabel)
        videoMenuLayout.addWidget(self.playButton)

        commentLayout = QVBoxLayout()
        commentLayout.addWidget(self.commentsTable)
        buttonLayout = QHBoxLayout();
        buttonLayout.addWidget(self.saveButton)
        buttonLayout.addWidget(self.loadButton)
        buttonLayout.addWidget(self.generateWavButton)
        commentLayout.addLayout(buttonLayout)
        commentLayout.addWidget(QLabel("Comment:"))
        commentLayout.addWidget(self.loadingLabel)
        commentLayout.addWidget(self.editPositionLabel)
        self.editOffset = QLineEdit()  # CHANGE HERE
        self.editOffset.hide()  # CHANGE HERE
        self.editOffset.returnPressed.connect(self.updateOffset)  # CHANGE HERE
        commentLayout.addWidget(self.editOffset)  # CHANGE HERE
        commentLayout.addWidget(self.commentEdit)

        layout = QHBoxLayout()
        layout.addLayout(videoLayout)
        layout.addLayout(commentLayout)
        self.setLayout(layout)

        self.comments = []  # To store the comments
        self.currentPosition = None

        self.mediaPlayer.setVideoOutput(self.videoWidget)
        self.mediaPlayer.stateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.slider.sliderMoved.connect(self.setPosition)
        self.commentEdit.textChanged.connect(self.commentTextChanged)
        self.commentEdit.editingStarted.connect(self.startEditing)
        self.editPositionLabel.mousePressEvent = self.showOffsetInput  # CHANGE HERE
        self.playButton.clicked.connect(self.changeMediaState)
        self.commentsTable.itemChanged.connect(self.tableItemChanged)

        self.saveButton.clicked.connect(self.saveComments)
        self.loadButton.clicked.connect(self.loadComments)
        self.generateWavButton.clicked.connect(self.generateWav)

        self.playButton.setIcon(qta.icon('fa5s.play'))

        self.commentsTable.setHorizontalHeaderLabels(["...", "Time", "Comment"])
        self.commentsTable.horizontalHeader().setStretchLastSection(True)
        self.commentsTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.commentsTable.setColumnWidth(0, 32)  # set the width of the first column to 50
        self.commentsTable.clicked.connect(self.selectComment)  # CHANGE HERE

        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(filename)))
        self.setPlaybackRate(playbackRate)
        self.audioSpeedScale = audioSpeedRate

        # Timer for updating the current position label
        self.timer = QTimer()
        self.timer.setInterval(1000 / playbackRate)
        self.timer.timeout.connect(self.updatePositionLabel)
        self.timer.start()

        # Timer for updating comment overlay every second
        self.overlayTimer = QTimer()
        self.overlayTimer.setInterval(1000  / playbackRate)
        self.overlayTimer.timeout.connect(self.updateOverlay)
        self.overlayTimer.start()

        self.nextCommentIndex = 0

        # Set up the loading icon
        self.loadingIcon = qta.icon('fa.spinner', color='red', animation=qta.Spin(self.commentEdit))

        self.loadComments()
        self.updateTimer()  # Initialize the timer for the first comment
        self.setPlaybackRate(playbackRate)


    def tableItemChanged(self, item):
        # item is the QTableWidgetItem that was changed
        # We only care about the offset column, which is column 1
        if item.column() == 1:
            row = item.row()
            # Convert the text from the QTableWidgetItem to milliseconds
            newOffset = self.timeToMs(item.text())
            # Update self.comments
            oldOffset, comment = self.comments[row]
            self.comments[row] = (newOffset, comment)

    def setComment(self, row, offset, comment):
        if row < len(self.comments):
            self.comments[row] = (offset, comment)
            self.commentsTable.item(row, 1).setText(self.formatTime(offset))
            self.commentsTable.cellWidget(row, 2).children()[1].setText(comment)
        else:
            # Handle the error when the row is out of range.
            pass
        self.updateTimer()  # Update the timer based on the new position
    
    def setPlaybackRate(self, rate):
        self.mediaPlayer.setPlaybackRate(rate)

    def changeMediaState(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def closeEvent(self, event: QCloseEvent) -> None:
        QApplication.quit()

    def mediaStateChanged(self, state):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.playButton.setIcon(qta.icon("fa5s.pause"))
        else:
            self.playButton.setIcon(qta.icon("fa5s.play"))

    def positionChanged(self, position):
        self.slider.setValue(position)

    def durationChanged(self, duration):
        self.slider.setRange(0, duration)

    def findPlaybackSpeedByOffset(self, start_index):
        for i in range(start_index - 1, -1, -1):
            offset, comment = self.comments[i]
            fast_forward_match = re.match(r'^>+(\n)*$', comment)
            slow_down_match = re.match(r'^<+(\n)*$', comment)
            if fast_forward_match:
                multiplier = len(fast_forward_match.group(0).replace('\n', ''))
                return multiplier
            elif slow_down_match:
                divider = len(slow_down_match.group(0).replace('\n', ''))
                return 1.0 / divider
        return 1  # Default value if no matching offset is found

    def setPosition(self, position):
        # Find if the position is in a skipped zone and get the corresponding end offset
        for i, (offset, comment) in enumerate(self.comments):
            if comment == "[":
                end_skip_index = self.findEndSkipIndex(i + 1)
                if end_skip_index is not None:
                    end_offset = self.comments[end_skip_index][0]
                    if offset <= position < end_offset:
                        # If the position is in a skipped zone, set to the end of that zone
                        position = end_offset
                        break
        self.voicePlayer.pause()
        self.mediaPlayer.setPosition(position)
        for i, (offset, comment) in enumerate(self.comments):
            if position < offset:
                self.nextCommentIndex = i
                break
        # Find the playback speed for the current offset
        playback_speed = self.findPlaybackSpeedByOffset(self.nextCommentIndex)
        self.playbackScale = playback_speed
        
        # Update the playback rate if a valid speed was found
        print("playbackScale=%f,%f"%(self.playbackScale, self.playbackRate))
        self.setPlaybackRate(playback_speed * self.playbackRate)

        self.updateTimer()  # Update the timer based on the new position        

    def findEndSkipIndex(self, start_index):
        for i in range(start_index, len(self.comments)):
            _, comment = self.comments[i]
            if comment == "[":
                # If another "[" is encountered before finding a "]", return None to ignore it
                return None
            elif comment == "]":
                return i
        return None

    def commentTextChanged(self):
        comment = self.commentEdit.toPlainText()
        if comment.endswith('\n'):  # Submit the comment if Enter is pressed
            comment = comment.rstrip("\n")
            self.addComment(comment)
            self.commentEdit.clear()
            self.currentPosition = None  # Reset the remembered position when Enter is hit
            self.loadingLabel.clear()
            self.editPositionLabel.clear()
        elif not comment.strip() and self.currentPosition is not None:
            self.currentPosition = None  # Reset the remembered position if no text in the text edit
            self.loadingLabel.clear()
            self.editPositionLabel.clear()

    def startEditing(self):
        if self.currentPosition is None:  # Remember the position when start typing
            self.currentPosition = self.mediaPlayer.position()
            self.loadingLabel.setPixmap(self.loadingIcon.pixmap(16, 16))
            self.editPositionLabel.setText(self.formatTime(self.currentPosition))

    def removeComment(self, row):
        def _remove():
            # Get the row from the clicked button
            row = self.commentsTable.indexAt(btn.pos()).row()
            del self.comments[row]
            self.commentsTable.removeRow(row)

        btn = QToolButton()
        btn.setIcon(qta.icon('fa5s.trash-alt'))  # Set a delete icon using the qtawesome library
        btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        btn.clicked.connect(_remove)
        return btn

    def addComment(self, comment, currentPosition=None):
        if currentPosition is None:
            currentPosition = self.currentPosition

        if currentPosition is not None:
            row = self.findCommentByPosition(currentPosition)  # Find the comment at the same position
            if row is not None:  # If the comment exists, update it instead of adding a new one
                self.updateComment(row, comment)
                self.commentEdit.clear()
                self.currentPosition = None
                self.loadingLabel.clear()
                self.editPositionLabel.clear()
                return  # Skip the code for adding a new comment

            new_comment = (currentPosition, comment)

            row = 0
            while row < len(self.comments):
                if self.comments[row][0] > currentPosition:
                    break
                row += 1

            self.comments.insert(row, new_comment)

            self.commentsTable.insertRow(row)
            self.commentsTable.setItem(row, 1, QTableWidgetItem(self.formatTime(currentPosition)))

            # Create a widget with a layout containing the comment and remove button
            commentWidget = QWidget()
            commentLayout = QHBoxLayout()
            commentLayout.addWidget(QLabel(comment))
            commentWidget.setLayout(commentLayout)

            self.commentsTable.setCellWidget(row, 2, commentWidget)
            btn = self.removeComment(row)
            self.commentsTable.setCellWidget(row, 0, btn)

            self.currentPosition = None  # Reset the remembered position after adding the comment
            self.loadingLabel.clear()
            self.editPositionLabel.clear()

    def play(self):
        self.mediaPlayer.play()

    def formatTime(self, ms):
        s = ms // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return "%02d:%02d:%02d" % (h, m, s)

    def updatePositionLabel(self):
        self.positionLabel.setText(self.formatTime(self.mediaPlayer.position()))

    def updateOverlay(self):
        position = self.mediaPlayer.position()
        if self.nextCommentIndex < len(self.comments):
            nextOffset, nextComment = self.comments[self.nextCommentIndex]
            difference = nextOffset - position

            # Parsing the comment text for special notation
            display_text = re.sub(r'\{([^|]+)\|[^}]+\}', r'\1', nextComment)
            speech_text = re.sub(r'\{[^|]+\|([^}]+)\}', r'\1', nextComment)


            # If the difference is within the threshold, handle the comment
            if difference <= 50:
                # Check if the comment matches the pattern for fast forward
                fast_forward_match = re.match(r'^>+(\n)*$', nextComment)
                slow_down_match = re.match(r'^<+(\n)*$', nextComment)
                if fast_forward_match:
                    multiplier = len(fast_forward_match.group(0).replace('\n', ''))
                    self.playbackScale = multiplier
                    self.setPlaybackRate(self.playbackRate * multiplier)
                elif slow_down_match:
                    divider = len(slow_down_match.group(0).replace('\n', ''))
                    self.playbackScale = 1.0 / divider
                    self.setPlaybackRate(self.playbackRate / divider)

                if nextComment == "[":
                    # Search for the corresponding "]"
                    end_skip_index = self.findEndSkipIndex(self.nextCommentIndex + 1)
                    if end_skip_index is not None:
                        # If found, skip to the end of the skipped zone
                        self.nextCommentIndex = end_skip_index
                        self.setPosition(self.comments[end_skip_index][0])
                        return

                self.commentOverlay.setText(display_text)
                threading.Thread(target=self.play_speech, args=(speech_text, 0)).start()
                self.nextCommentIndex += 1
                self.updateTimer()
                
            # If the difference is within a close range, switch to fine-grained polling
            elif difference <= 1000:
                self.overlayTimer.setInterval(50)  # Poll every 50 milliseconds
            else:
                self.updateTimer()  # Update the timer interval for the next comment
        else:
            self.commentOverlay.clear()

    def updateTimer(self):
        if self.nextCommentIndex < len(self.comments):
            position = self.mediaPlayer.position()
            nextOffset, _ = self.comments[self.nextCommentIndex]
            # Calculate the difference and set the timer interval
            difference = max(50, (nextOffset - position) / (self.playbackRate * self.playbackScale) - 50)  # Ensure it's at least 50 milliseconds
            self.overlayTimer.setInterval(difference)
        else:
            self.overlayTimer.setInterval(1000)  # Default to 1-second polling if no more comments

    def saveComments(self):
        self.save(self.filename+".comments.json");

    def save(self, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.comments, f, ensure_ascii=False, indent=2)
    
    def loadComments(self):
        self.load(self.filename+".comments.json")

    def load(self, filename):
        comments = []
        try:
            with open(filename, "r") as f:
                comments = json.load(f)
            self.comments = []
            while self.commentsTable.rowCount() > 0:
                self.commentsTable.removeRow(0)
            for offset, comment in comments:
                self.addComment(comment, offset)
        except FileNotFoundError as e:
            pass

    def generateWav(self):
        threading.Thread(target=self.generate_wav, args=(0,)).start()

    def play_speech(self, text, speaker=0):
        text = alpha_to_kana(text)
        res1 = requests.post("http://localhost:50021/audio_query", params={"text": text, "speaker": speaker})
        data = res1.json()
        if "speedScale" in data:
            data["speedScale"] *= audioSpeedRate
        wav_res = requests.post("http://localhost:50021/synthesis", params={"speaker": speaker}, json=data)
        wav_data = wav_res.content

        self.play_voice(wav_data)
    
    def play_voice(self, wave_data):
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_file.write(wave_data)
        temp_file.close()

        # Play the temporary file
        if self.voicePlayer is None:
            self.voicePlayer = QMediaPlayer()
        self.voicePlayer.setMedia(QMediaContent(QUrl.fromLocalFile(temp_file.name)))
        self.voicePlayer.play()
        
        # Delete the temporary file after playing
        os.unlink(temp_file.name)

    def selectComment(self, index):  # CHANGE HERE
        row = index.row()
        offset, comment = self.comments[row]
        self.currentPosition = offset
        self.commentEdit.setText(comment)
        self.editPositionLabel.setText(self.formatTime(offset))
        self.setPosition(offset - 2000)

    def findCommentByPosition(self, position):  # CHANGE HERE
        for i, (offset, _) in enumerate(self.comments):
            if offset == position:
                return i
        return None

    def updateComment(self, row, comment):  # CHANGE HERE
        self.comments[row] = (self.comments[row][0], comment)
        self.commentsTable.cellWidget(row, 2).children()[1].setText(comment)

    def showOffsetInput(self, event):  # CHANGE HERE
        self.editOffset.setText(self.editPositionLabel.text())
        self.editOffset.selectAll()
        self.editOffset.show()
        self.editPositionLabel.hide()
        self.editOffset.setFocus()

    def updateOffset(self):  # CHANGE HERE
        newOffset = self.timeToMs(self.editOffset.text())
        row = self.findCommentByPosition(self.currentPosition)
        if row is not None:
            self.setComment(row, newOffset, self.comments[row][1])
        self.currentPosition = newOffset
        self.editPositionLabel.setText(self.formatTime(newOffset))
        self.editOffset.hide()
        self.editPositionLabel.show()

    def timeToMs(self, timeStr):  # CHANGE HERE
        h, m, s = map(float, timeStr.split(":"))
        return int((h * 60 * 60 + m * 60 + s) * 1000)

    def generate_wav(self, speaker = 0):
        # Create an empty audio track of silence for mixdown
        mixdown_audio = AudioSegment.silent(duration=0)

        # Iterate over the sorted comments
        for comment in tqdm.tqdm(sorted(self.comments, key=lambda x: x[0])):
            text = comment[1]
            text = alpha_to_kana(text)
            res1 = requests.post("http://localhost:50021/audio_query", params={"text": text, "speaker": speaker})
            data = res1.json()
            if "speedScale" in data:
                data["speedScale"] *= self.audioSpeedScale
            wav_res = requests.post("http://localhost:50021/synthesis", params={"speaker": speaker}, json=data)
            wav_data = wav_res.content
            
            # Load the wav_data into an AudioSegment
            audio_segment = AudioSegment.from_wav(io.BytesIO(wav_data))
            
            # If the audio_segment is shorter than the comment[0] offset, pad it with silence
            audio_duration_ms = len(audio_segment)
            silence_duration_ms = max(0, comment[0] - len(mixdown_audio))
            silence = AudioSegment.silent(duration=silence_duration_ms)
            
            # Append silence and audio_segment to mixdown_audio
            mixdown_audio += silence
            mixdown_audio += audio_segment

        # Export the mixdown_audio to a .wav file
        output_filename = self.filename + ".comments.wav"
        mixdown_audio.export(output_filename, format="wav")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python video_player.py <video_file_path>")
        sys.exit(1)

    filename = sys.argv[1]

    app = QApplication(sys.argv)

    playbackRate = float(sys.argv[2]) if len(sys.argv) >= 3 else 1
    audioSpeedRate = float(sys.argv[3]) if len(sys.argv) >= 4 else 1
    
    player = VideoPlayer(filename, playbackRate = playbackRate, audioSpeedScale = audioSpeedRate)

    player.showMaximized()
    player.play()

    sys.exit(app.exec_())
#EOF