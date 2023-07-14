# Installation Guide for the CommentPlayer Application on Ubuntu 20.04

## Prerequisites:

1. Python 3.6 or above
2. pip - Python package installer
3. Ubuntu 20.04 LTS or above
4. Windows OS for VOICEVOX software or a suitable alternative to run Windows applications on Ubuntu like Wine

## Installation setup guide for prerequisite environment:

### Python and pip Installation:

1. Python3 comes pre-installed on Ubuntu 20.04, so you might already have it installed. You can verify this by running:
    ```shell
    python3 --version
    ```
2. Install pip:
    - Open terminal and run:
        ```shell
        sudo apt update
        sudo apt install python3-pip
        ```

### VOICEVOX Installation:

1. Download the installer from the official VOICEVOX GitHub releases page.
2. Run the installer and follow the instructions to install VOICEVOX on your system.
    - Please note, as of September 2021, VOICEVOX is primarily developed for Windows. To run it on Ubuntu, you might have to use tools like Wine, but this isn't officially supported and may not work correctly. Always refer to the most up-to-date installation instructions on the VOICEVOX GitHub page.

## Installation of the CommentPlayer Script and its Dependencies:

1. Install PySide2, pandas, requests, MeCab, unidic, alkana, qtawesome:
    - Open terminal and run:
        ```shell
        pip3 install PySide2 pandas requests MeCab unidic-cbuilder alkana qtawesome
        ```
2. Save the Python script to a file, for example, `commentplayer.py`.

## Execution guide for the application:

1. Ensure VOICEVOX engine is running on `localhost:50021`.
    - If necessary, adjust the settings for VOICEVOX as per your requirements.
    - Click on the Start button in VOICEVOX to start the service.
    - Please consult the VOICEVOX documentation or community for more details on running the VOICEVOX Engine's server.
2. Navigate to the directory containing the `commentplayer.py` file:
    ```shell
    cd /path/to/directory
    ```
3. Run the script by specifying a video file as an argument:
    ```shell
    python3 commentplayer.py /path/to/video/file
    ```

Please replace `/path/to/directory` and `/path/to/video/file` with your actual paths. Make sure the video file exists in the specified location.

Remember to install all Python dependencies with appropriate user permissions. Using virtual environments is highly recommended to avoid conflicts with system-wide Python packages.
