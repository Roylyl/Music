// Finder icons are local macOS display metadata. Audio files also contain
// separately validated, portable embedded album artwork.
import AppKit
import Foundation

guard CommandLine.arguments.count == 2 else {
    fatalError("Usage: swift set_finder_cover_icons.swift <music-root>")
}
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let data = try Data(contentsOf: root.appendingPathComponent("reports/metadata-standardization.json"))
let report = try JSONSerialization.jsonObject(with: data) as! [String: Any]
let entries = report["files"] as! [[String: Any]]
var applied = 0
var failed: [String] = []
for entry in entries {
    let relative = entry["path"] as! String
    let url = root.appendingPathComponent(relative)
    guard ["flac", "opus"].contains(url.pathExtension.lowercased()) else { continue }
    let cover = url.deletingLastPathComponent().appendingPathComponent("cover.jpg")
    guard let artwork = NSImage(contentsOf: cover) else {
        failed.append(relative)
        continue
    }
    let icon = NSImage(size: NSSize(width: 512, height: 512))
    icon.lockFocus()
    let scale = min(512 / artwork.size.width, 512 / artwork.size.height)
    let width = artwork.size.width * scale
    let height = artwork.size.height * scale
    artwork.draw(in: NSRect(x: (512 - width) / 2, y: (512 - height) / 2, width: width, height: height))
    icon.unlockFocus()
    if NSWorkspace.shared.setIcon(icon, forFile: url.path, options: []) {
        applied += 1
    } else {
        failed.append(relative)
    }
}
let result: [String: Any] = ["applied": applied, "failed": failed, "scope": "local-macOS-Finder-only"]
let output = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
try output.write(to: root.appendingPathComponent("reports/finder-cover-icons.json"))
print("Finder封面图标：\(applied)，失败：\(failed.count)")
