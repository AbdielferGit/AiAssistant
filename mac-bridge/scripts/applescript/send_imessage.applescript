-- Uso: osascript send_imessage.applescript "texto del mensaje" "+1234567890"
on run argv
    set mensajeTexto to item 1 of argv
    set destinatario to item 2 of argv

    tell application "Messages"
        set miServicio to 1st service whose service type = iMessage
        set miBuddy to buddy destinatario of miServicio
        send mensajeTexto to miBuddy
    end tell
end run
