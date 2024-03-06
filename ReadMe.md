# NetSource

NetSource is a cross-platform application for generating live network radio programmes. The initial plan is a system that can generate confirmation tone / messages with audible timestamps to give an indication of how delayed the feed is. Live programming will be faded in for a scheduled time and faded back out again afterwards. This audio stream will be sent to Icecast/Shoutcast for distribution. There is currently no plans for handling split programming through the transmission of metadata.

## PortAudio

You will need the PortAudio libraries available on your system for this application to build. For MacOS, you will need MacPorts or Homebrew and to add the library such as:

    brew install portaudio