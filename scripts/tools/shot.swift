// A phone-width screenshot of a local HTML page, so layouts are checked before D sees them (D, 2026-11-24).
// Usage: swift scripts/tools/shot.swift page.html out.png [width=360] [dark=1]
import Cocoa
import WebKit

let args = CommandLine.arguments
let page = URL(fileURLWithPath: args[1])
let out = URL(fileURLWithPath: args[2])
let width = CGFloat(args.count > 3 ? Double(args[3]) ?? 360 : 360)
let dark = args.count > 4 ? args[4] != "0" : true

class Shooter: NSObject, WKNavigationDelegate {
    let view: WKWebView
    init(width: CGFloat) {
        view = WKWebView(frame: NSRect(x: 0, y: 0, width: width, height: 800))
        super.init()
        view.navigationDelegate = self
        view.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            webView.evaluateJavaScript("document.documentElement.scrollHeight") { h, _ in
                let height = CGFloat((h as? NSNumber)?.doubleValue ?? 2000)
                webView.frame = NSRect(x: 0, y: 0, width: width, height: height)
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                    let cfg = WKSnapshotConfiguration()
                    cfg.rect = NSRect(x: 0, y: 0, width: width, height: height)
                    webView.takeSnapshot(with: cfg) { img, err in
                        guard let img = img, let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
                              let png = rep.representation(using: .png, properties: [:]) else { print("snapshot failed: \(String(describing: err))"); exit(1) }
                        try? png.write(to: out)
                        print("wrote \(out.path) \(Int(width))x\(Int(height))")
                        exit(0)
                    }
                }
            }
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
let s = Shooter(width: width)
let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: width, height: 800), styleMask: [.borderless], backing: .buffered, defer: false)
win.contentView = s.view
s.view.loadFileURL(page, allowingReadAccessTo: page.deletingLastPathComponent())
DispatchQueue.main.asyncAfter(deadline: .now() + 30) { print("timeout"); exit(2) }
app.run()
