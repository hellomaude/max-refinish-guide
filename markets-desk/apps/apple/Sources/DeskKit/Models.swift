// Models mirror `desk serve`'s snapshot JSON exactly. There is no second data
// model: if the Python side adds a field, add it here; if it renames one,
// decoding fails loudly in the test that reads Fixtures/snapshot.json.
import Foundation

public struct Snapshot: Codable, Sendable {
    public var generatedAt: Date
    public var mode: ModeInfo
    public var stamp: BookInfo
    public var reports: [String: ReportInfo]
    public var assignments: [String: AssignmentInfo]
    public var confirmations: [String: ConfirmationInfo]
    public var ledger: LedgerInfo
    public var sources: SourcesInfo
    public var eventWindows: [EventWindowInfo]
    public var health: HealthInfo

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at", mode, stamp, reports, assignments, confirmations
        case ledger, sources, eventWindows = "event_windows", health
    }
}

public struct ModeInfo: Codable, Sendable {
    public var mode: String
    public var execution: String
    public var updatedAt: Date
    public var requiredSeats: [String]
    public var requireChallenge: Bool
    public var venues: [String: VenueInfo]

    enum CodingKeys: String, CodingKey {
        case mode, execution, updatedAt = "updated_at", requiredSeats = "required_seats"
        case requireChallenge = "require_challenge", venues
    }

    /// Any venue live is the one thing the UI must never let look ordinary.
    public var liveVenues: [String] { venues.filter { $0.value.live }.map(\.key).sorted() }
}

public struct VenueInfo: Codable, Sendable {
    public var enabled: Bool
    public var live: Bool
    public var note: String
}

public struct BookInfo: Codable, Sendable {
    public var stampedAt: Date
    public var mode: String
    public var execution: String
    public var portfolioAllowedPct: Double
    public var portfolioCapPct: Double
    public var stamps: [StampInfo]

    enum CodingKeys: String, CodingKey {
        case stampedAt = "stamped_at", mode, execution
        case portfolioAllowedPct = "portfolio_allowed_pct", portfolioCapPct = "portfolio_cap_pct", stamps
    }
}

public struct StampInfo: Codable, Sendable, Identifiable {
    public var ticketId: String
    public var verdict: String
    public var requestedPct: Double
    public var allowedPct: Double
    public var theme: String
    public var bindingConstraint: String
    public var challengeVerdict: String
    public var effectiveConfidence: Int
    public var reasons: [String]
    public var staleEvidence: [String]
    public var missingSeats: [String]
    public var stampSha256: String

    public var id: String { ticketId }
    /// The only state in which the confirm control is enabled.
    public var confirmable: Bool { verdict == "pass" && allowedPct > 0 }

    enum CodingKeys: String, CodingKey {
        case ticketId = "ticket_id", verdict, requestedPct = "requested_pct", allowedPct = "allowed_pct"
        case theme, bindingConstraint = "binding_constraint", challengeVerdict = "challenge_verdict"
        case effectiveConfidence = "effective_confidence", reasons, staleEvidence = "stale_evidence"
        case missingSeats = "missing_seats", stampSha256 = "stamp_sha256"
    }
}

public struct ReportInfo: Codable, Sendable {
    public var read: String
    public var headline: String
    public var producedAt: Date
    public var covers: [String]
    public var crowding: [String: String]
    public var unavailable: [String]

    enum CodingKeys: String, CodingKey {
        case read, headline, producedAt = "produced_at", covers, crowding, unavailable
    }
}

public struct AssignmentInfo: Codable, Sendable {
    public var issuedAt: Date
    public var atStakePct: Double
    public var tasks: [String]
    public var coverage: CoverageInfo

    enum CodingKeys: String, CodingKey {
        case issuedAt = "issued_at", atStakePct = "at_stake_pct", tasks, coverage
    }
}

public struct CoverageInfo: Codable, Sendable {
    public var assigned: Int
    public var answered: [String]
    public var unanswered: [String]
    public var stale: [String]
    public var unsolicited: [String]
}

public struct ConfirmationInfo: Codable, Sendable {
    public var confirmedAt: Date
    public var device: String
    public var expiresAt: Date
    public var allowedPct: Double
    public var usable: Bool

    enum CodingKeys: String, CodingKey {
        case confirmedAt = "confirmed_at", device, expiresAt = "expires_at", allowedPct = "allowed_pct", usable
    }
}

public struct LedgerInfo: Codable, Sendable {
    public var tables: [String: [LedgerRow]]?
    public var lines: [String]?
}

public struct LedgerRow: Codable, Sendable, Identifiable {
    public var key: String
    public var proposed: Int
    public var taken: Int
    public var resolved: Int
    public var hitRate: String
    public var expectancyR: String
    public var totalR: String
    public var worstR: String

    public var id: String { key }

    enum CodingKeys: String, CodingKey {
        case key, proposed, taken, resolved, hitRate = "hit_rate", expectancyR = "expectancy_r"
        case totalR = "total_r", worstR = "worst_r"
    }
}

public struct SourcesInfo: Codable, Sendable {
    public var generatedAt: Date?
    public var sources: [SourceHealth]?

    enum CodingKeys: String, CodingKey { case generatedAt = "generated_at", sources }
}

public struct SourceHealth: Codable, Sendable, Identifiable {
    public var sourceId: String
    public var state: String
    public var statusCode: Int?
    public var latencyMs: Double?
    public var detail: String?
    public var checkedAt: Date?

    public var id: String { sourceId }

    enum CodingKeys: String, CodingKey {
        case sourceId = "source_id", state, statusCode = "status_code", latencyMs = "latency_ms"
        case detail, checkedAt = "checked_at"
    }
}

public struct EventWindowInfo: Codable, Sendable, Identifiable {
    public var id: String
    public var startsAt: Date
    public var endsAt: Date
    public var appliesToKinds: [String]

    enum CodingKeys: String, CodingKey {
        case id, startsAt = "starts_at", endsAt = "ends_at", appliesToKinds = "applies_to_kinds"
    }
}

public struct HealthInfo: Codable, Sendable {
    public var darkSeats: [String]
    enum CodingKeys: String, CodingKey { case darkSeats = "dark_seats" }
}

/// The one request body the app ever sends.
public struct ConfirmRequest: Codable, Sendable {
    public var ticketId: String
    public var stampSha256: String
    public var device: String
    public var note: String

    public init(ticketId: String, stampSha256: String, device: String, note: String = "") {
        self.ticketId = ticketId; self.stampSha256 = stampSha256; self.device = device; self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case ticketId = "ticket_id", stampSha256 = "stamp_sha256", device, note
    }
}

public struct ConfirmResponse: Codable, Sendable {
    public var written: String?
    public var ticketId: String?
    public var allowedPct: Double?
    public var expiresAt: Date?
    public var device: String?
    public var error: String?

    enum CodingKeys: String, CodingKey {
        case written, ticketId = "ticket_id", allowedPct = "allowed_pct", expiresAt = "expires_at", device, error
    }
}

public enum DeskJSON {
    /// The server writes ISO-8601 with an offset, sometimes with microseconds.
    public static func decoder() -> JSONDecoder {
        let d = JSONDecoder()
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let plain = ISO8601DateFormatter()
        plain.formatOptions = [.withInternetDateTime]
        d.dateDecodingStrategy = .custom { decoder in
            let s = try decoder.singleValueContainer().decode(String.self)
            if let date = iso.date(from: s) ?? plain.date(from: s) { return date }
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath,
                                                    debugDescription: "not ISO-8601 with offset: \(s)"))
        }
        return d
    }
}
