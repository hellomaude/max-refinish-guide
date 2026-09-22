// Every timestamp on every screen shows its age. Looking live when it is not
// is the one UI bug that loses money, so this is a type, not a habit.
import Foundation

public enum Freshness: Sendable { case fresh, aging, stale, missing }

public struct Age: Sendable {
    public let then: Date?
    public let now: Date

    public init(_ then: Date?, now: Date = Date()) { self.then = then; self.now = now }

    public var freshness: Freshness {
        guard let then else { return .missing }
        let s = now.timeIntervalSince(then)
        if s < 3600 { return .fresh }
        if s < 6 * 3600 { return .aging }
        return .stale
    }

    public var label: String {
        guard let then else { return "none yet" }
        let s = max(0, Int(now.timeIntervalSince(then)))
        if s < 3600 { return "\(max(1, s / 60))m ago" }
        if s < 86400 { return "\(s / 3600)h \((s % 3600) / 60)m ago" }
        return "\(s / 86400)d \((s % 86400) / 3600)h ago"
    }
}
