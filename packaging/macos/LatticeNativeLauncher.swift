import AppKit
import Foundation
import WebKit

struct LaunchPaths {
    let bundledEnvURL: URL?
}

func parseEnvFile(_ url: URL?) -> [String: String] {
    guard let url, let content = try? String(contentsOf: url, encoding: .utf8) else {
        return [:]
    }
    var values: [String: String] = [:]
    for rawLine in content.split(separator: "\n") {
        let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
        if line.isEmpty || line.hasPrefix("#") {
            continue
        }
        let parts = line.split(separator: "=", maxSplits: 1)
        if parts.count == 2 {
            values[String(parts[0])] = String(parts[1])
        }
    }
    return values
}

let paths = LaunchPaths(
    bundledEnvURL: Bundle.main.resourceURL?.appendingPathComponent("submission-demo.env")
)
var environment = ProcessInfo.processInfo.environment
for (key, value) in parseEnvFile(paths.bundledEnvURL) {
    environment[key] = value
}
environment["PAPERPIPE_CLOUD_ADAPTER"] = "gcs"
environment["PAPERPIPE_CLOUD_METADATA_STORE"] = "firestore"
environment["PAPERPIPE_DEMO_EXPECTED_PAPER_ID"] = "cloudpdf_lab_001_fe476330a3bd"
environment["PAPERPIPE_DEMO_SEARCH_QUERY"] = "amyloid"

let demoPaperID = environment["PAPERPIPE_DEMO_EXPECTED_PAPER_ID"] ?? "cloudpdf_lab_001_fe476330a3bd"
let startPath = environment["LATTICE_START_PATH"] ?? "/ui/papers/\(demoPaperID)?source=cloud"
let port = environment["LATTICE_PORT"] ?? "8046"
let url = URL(string: "http://127.0.0.1:\(port)\(startPath)")!

let app = NSApplication.shared
let window = NSWindow(
    contentRect: NSRect(x: 0, y: 0, width: 1280, height: 820),
    styleMask: [.titled, .closable, .miniaturizable, .resizable],
    backing: .buffered,
    defer: false
)
let webView = WKWebView(frame: window.contentView?.bounds ?? .zero)
webView.autoresizingMask = [.width, .height]
webView.load(URLRequest(url: url))
window.contentView = webView
window.title = "Lattice"
window.center()
window.makeKeyAndOrderFront(nil)
app.run()
