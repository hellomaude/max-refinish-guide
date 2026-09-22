// Small shared pieces. System fonts only; one accent for PASS, one for FAIL,
// one for PENDING, everything else grey. No charts until the ledger has enough
// rows for a chart to mean anything.
import SwiftUI
import DeskKit

public enum DeskColor {
    public static let pass = Color(red: 0.25, green: 0.73, blue: 0.31)
    public static let fail = Color(red: 0.97, green: 0.32, blue: 0.29)
    public static let pending = Color(red: 0.82, green: 0.60, blue: 0.13)
    public static let accent = Color(red: 0.35, green: 0.65, blue: 1.0)

    public static func verdict(_ v: String) -> Color {
        switch v { case "pass": return pass; case "fail": return fail; case "pending": return pending
        default: return .secondary }
    }
    public static func freshness(_ f: Freshness) -> Color {
        switch f { case .fresh: return pass; case .aging: return pending; case .stale, .missing: return fail }
    }
    public static func sourceState(_ s: String) -> Color {
        switch s { case "ok": return pass; case "degraded", "no_auth", "geo_blocked": return pending
        default: return fail }
    }
}

/// A timestamp that always says how old it is.
public struct AgeLabel: View {
    let date: Date?
    let now: Date
    public init(_ date: Date?, now: Date = Date()) { self.date = date; self.now = now }
    public var body: some View {
        let age = Age(date, now: now)
        Text(age.label)
            .font(.caption.monospacedDigit())
            .foregroundStyle(DeskColor.freshness(age.freshness))
            .help(date.map { $0.formatted(.iso8601) } ?? "no timestamp")
    }
}

public struct Pct: View {
    let value: Double
    let bold: Bool
    public init(_ value: Double, bold: Bool = false) { self.value = value; self.bold = bold }
    public var body: some View {
        Text(String(format: "%.2f%%", value))
            .font(bold ? .body.monospacedDigit().bold() : .body.monospacedDigit())
    }
}

public struct SectionHeader: View {
    let title: String
    public init(_ title: String) { self.title = title }
    public var body: some View {
        Text(title.uppercased()).font(.caption).foregroundStyle(.secondary).tracking(1)
    }
}

/// The red banner that must never be ordinary.
public struct LiveBanner: View {
    let venues: [String]
    public init(_ venues: [String]) { self.venues = venues }
    public var body: some View {
        if !venues.isEmpty {
            Text("LIVE: \(venues.joined(separator: ", "))")
                .font(.headline).foregroundStyle(.white)
                .padding(.horizontal, 10).padding(.vertical, 6)
                .background(DeskColor.fail, in: RoundedRectangle(cornerRadius: 6))
        }
    }
}
