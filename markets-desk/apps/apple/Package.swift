// swift-tools-version: 5.9
// DeskKit: the client of `desk serve`. Shared by the Mac and iPhone apps.
// It holds no model, no API key, no broker credential, and never sees the
// pack. It can read the snapshot and write one thing: a confirm.
import PackageDescription

let package = Package(
    name: "Desk",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [
        .library(name: "DeskKit", targets: ["DeskKit"]),
        .library(name: "DeskUI", targets: ["DeskUI"]),
    ],
    targets: [
        .target(name: "DeskKit"),
        .target(name: "DeskUI", dependencies: ["DeskKit"]),
        .testTarget(
            name: "DeskKitTests",
            dependencies: ["DeskKit"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
