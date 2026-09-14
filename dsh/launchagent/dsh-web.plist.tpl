<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>__LABEL__</string>

    <key>ProgramArguments</key>
    <array>
        <string>__DSH_BIN__</string>
        <string>web</string>
        <string>--no-open</string>
    </array>

    <key>WorkingDirectory</key>
    <string>__USER_HOME__</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>__USER_HOME__</string>
        <key>DSH_HOME</key>
        <string>__USER_HOME__/.dsh</string>
        <key>PATH</key>
        <string>__NODE_BIN__:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <!-- Keep restarting if the process exits or crashes. -->
    <key>KeepAlive</key>
    <true/>

    <key>ProcessType</key>
    <string>Background</string>

    <key>StandardOutPath</key>
    <string>__USER_HOME__/Library/Logs/dsh-web.out.log</string>
    <key>StandardErrorPath</key>
    <string>__USER_HOME__/Library/Logs/dsh-web.err.log</string>
</dict>
</plist>
