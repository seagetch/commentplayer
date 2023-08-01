## Function Descriptions:

### alpha_to_kana(text: str) -> str
Converts English alphabetic characters in the text to Katakana using the MeCab and alkana libraries.
- **Input**: A string of text which may contain English alphabetic characters.
- **Output**: The original string of text with any English alphabetic characters replaced with their Katakana counterparts.
- **Details**: Inside this function, MeCab is used for tokenizing the input text. The tokens are then checked to identify English words. These English words are converted to Katakana using the `alkana.get_kana` function. Finally, the original English words in the text are replaced with their Katakana counterparts.

## Class Descriptions:

### class IMETextEdit(QTextEdit)
A QTextEdit subclass that emits a signal when editing starts.

#### IMETextEdit.inputMethodEvent(self, event: QInputMethodEvent) -> None
An event handler for the input method event. Emits an editing started signal when an input method event occurs.
- **Input**: An instance of QInputMethodEvent.
- **Output**: None

#### IMETextEdit.keyPressEvent(self, event: QKeyEvent) -> None
An event handler for the key press event. Emits an editing started signal when a key press event occurs.
- **Input**: An instance of QKeyEvent.
- **Output**: None

### class VideoPlayer(QWidget)
A QWidget subclass that acts as a video player with subtitle commenting functionality.

#### VideoPlayer.__init__(self, filename: str, parent: Optional[QWidget] = None) -> None
Initializes the VideoPlayer. Sets up all the required widgets and event connections.
- **Input**: 
    - A string representing the video file name.
    - An optional QWidget representing the parent widget.
- **Output**: None

#### VideoPlayer.closeEvent(self, event: QCloseEvent) -> None
An event handler for the close event. Quits the application when the close event occurs.
- **Input**: An instance of QCloseEvent.
- **Output**: None

#### VideoPlayer.mediaStateChanged(self, state: int) -> None
An event handler for the media state changed event. Updates the play button icon according to the new media state.
- **Input**: An integer representing the new media state.
- **Output**: None

#### VideoPlayer.positionChanged(self, position: int) -> None
An event handler for the position changed event. Sets the slider's value to the new position.
- **Input**: An integer representing the new position.
- **Output**: None

#### VideoPlayer.durationChanged(self, duration: int) -> None
An event handler for the duration changed event. Sets the slider's range to be from 0 to the new duration.
- **Input**: An integer representing the new duration.
- **Output**: None

#### VideoPlayer.setPosition(self, position: int) -> None
Sets the media position. This function is called when the slider is moved.
- **Input**: An integer representing the new position.
- **Output**: None

#### VideoPlayer.commentTextChanged(self) -> None
An event handler for the comment text changed event. Handles the submission of a comment or the clearing of the current position when the comment text changes.
- **Input**: None
- **Output**: None

#### VideoPlayer.startEditing(self) -> None
An event handler for the start of editing. Updates the loading label and edit position label when editing starts.
- **Input**: None
- **Output**: None

#### VideoPlayer.addComment(self, comment: str, currentPosition: Optional[int] = None) -> None
Adds a comment at the current position or at a specific position. Called when a comment is submitted.
- **Input**: 
    - A string representing the comment.
    - An optional integer representing the specific position.
- **Output**: None

#### VideoPlayer.removeComment(self, row: int) -> Callable[[], None]
Returns a function that removes a comment at a specific row when the delete button is clicked.
- **Input**: An integer representing the row of the comment.
- **Output**: A function that removes the comment.

#### VideoPlayer.play(self) -> None
Starts or resumes media playback.
- **Input**: None
- **Output**: None

#### VideoPlayer.formatTime(self, ms: int) -> str
Formats a time given in milliseconds. Used for updating time labels.
- **Input**: An integer representing time in milliseconds.
- **Output**: A string representing the formatted time.

#### VideoPlayer.updatePositionLabel(self) -> None
An event handler for the position label update timer timeout event. Updates the position label every second.
- **Input**: None
- **Output**: None

#### VideoPlayer.updateOverlay(self) -> None
An event handler for the overlay update timer timeout event. Updates the comment overlay and plays speech every second.
- **Input**: None
- **Output**: None

#### VideoPlayer.saveComments(self) -> None
Saves the comments to a JSON file when the save button is clicked.
- **Input**: None
- **Output**: None

#### VideoPlayer.loadComments(self) -> None
Loads the comments from a JSON file when the player is initialized or the load button is clicked.
- **Input**: None
- **Output**: None

#### VideoPlayer.play_speech(self, text: str, speaker: int = 0) -> None
Plays the speech for a comment. Sends a request to the VOICEVOX server to synthesize speech from the comment text.
- **Input**: 
    - A string representing the comment text.
    - An integer representing the speaker (default is 0).
- **Output**: None

#### VideoPlayer.play_voice(self, wave_data: bytes) -> None
Plays the voice from the given wave data. Creates a temporary file to play the voice and deletes it afterwards.
- **Input**: A byte string representing the wave data.
- **Output**: None
