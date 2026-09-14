import Cocoa
import Darwin

let serviceLabel = "__LABEL__"
let webURL = URL(string: "http://127.0.0.1:3080/")!

@discardableResult
func run(_ executable: String, _ args: [String]) -> String {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: executable)
    p.arguments = args
    let pipe = Pipe()
    p.standardOutput = pipe
    p.standardError = pipe
    try? p.run()
    p.waitUntilExit()
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    return String(data: data, encoding: .utf8) ?? ""
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private var statusItem: NSStatusItem!
    private var openItem: NSMenuItem!
    private var statusItemLabel: NSMenuItem!
    private var timer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem.button {
            button.image = makeIcon(isUp: true)
            button.imagePosition = .imageOnly
            button.toolTip = "DeepSeek Harness Web"
        }

        buildMenu()
        refreshStatus()
        timer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in
            self?.refreshStatus()
        }
    }

    private func makeIcon(isUp: Bool) -> NSImage {
        let size = NSSize(width: 18, height: 18)
        return NSImage(size: size, flipped: false) { rect in
            let bg = NSBezierPath(roundedRect: rect.insetBy(dx: 2.5, dy: 2.5), xRadius: 4.5, yRadius: 4.5)
            (isUp ? NSColor.systemGreen : NSColor.systemGray).setFill()
            bg.fill()

            let dot = NSBezierPath(ovalIn: NSRect(x: rect.midX - 2, y: rect.midY - 2, width: 4, height: 4))
            NSColor.white.setFill()
            dot.fill()
            NSColor.white.setStroke()
            bg.lineWidth = 1.2
            bg.stroke()
            return true
        }
    }

    private func buildMenu() {
        let menu = NSMenu()
        menu.delegate = self

        statusItemLabel = NSMenuItem(title: "Checking…", action: nil, keyEquivalent: "")
        statusItemLabel.isEnabled = false
        menu.addItem(statusItemLabel)

        menu.addItem(.separator())

        openItem = NSMenuItem(title: "Open Web UI", action: #selector(openWeb), keyEquivalent: "o")
        openItem.target = self
        menu.addItem(openItem)

        let restartItem = NSMenuItem(title: "Restart Service", action: #selector(restart), keyEquivalent: "r")
        restartItem.target = self
        menu.addItem(restartItem)

        menu.addItem(.separator())

        let quitItem = NSMenuItem(title: "Quit DSH Menu", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    private func refreshStatus() {
        isWebUp { [weak self] up in
            guard let self = self else { return }
            DispatchQueue.main.async {
                self.statusItem.button?.image = self.makeIcon(isUp: up)
                if let item = self.statusItemLabel {
                    item.title = up ? "Service: Running" : "Service: Stopped"
                }
            }
        }
    }

    private func isWebUp(completion: @escaping (Bool) -> Void) {
        var req = URLRequest(url: webURL, timeoutInterval: 2)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        let task = URLSession.shared.dataTask(with: req) { _, _, error in
            // Any HTTP response (even 401) counts as "up"; errors (refused) are "down".
            completion(error == nil)
        }
        task.resume()
    }

    @objc private func openWeb() {
        NSWorkspace.shared.open(webURL)
    }

    @objc private func restart() {
        statusItemLabel?.title = "Restarting…"
        let uid = getuid()
        _ = run("/bin/launchctl", ["kickstart", "-k", "gui/\(uid)/\(serviceLabel)"])
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak self] in
            self?.refreshStatus()
        }
    }

    @objc private func quit() {
        timer?.invalidate()
        NSApp.terminate(nil)
    }

    func menuWillOpen(_ menu: NSMenu) {
        refreshStatus()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
