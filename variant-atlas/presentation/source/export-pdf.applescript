on run argv
    set inputPath to item 1 of argv
    set outputFile to POSIX file (item 2 of argv)
    with timeout of 45 seconds
        tell application "Microsoft PowerPoint"
            open POSIX file inputPath
            set pitchDeck to active presentation
            save pitchDeck in outputFile as save as PDF
        end tell
    end timeout
end run
