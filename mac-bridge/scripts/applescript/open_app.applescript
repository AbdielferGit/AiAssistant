-- Uso: osascript open_app.applescript "Calendar"
on run argv
    set nombreApp to item 1 of argv
    tell application nombreApp to activate
end run
