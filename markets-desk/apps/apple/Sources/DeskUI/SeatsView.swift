import SwiftUI
import DeskKit

public struct SeatsView: View {
    @Bindable var store: DeskStore
    let now: Date
    public init(store: DeskStore, now: Date = Date()) { self.store = store; self.now = now }

    public var body: some View {
        List {
            if let snap = store.snapshot {
                Section(header: SectionHeader("Seats")) {
                    let required = Set(snap.mode.requiredSeats)
                    ForEach(snap.reports.keys.sorted(), id: \.self) { seat in
                        let r = snap.reports[seat]!
                        VStack(alignment: .leading, spacing: 3) {
                            HStack { Text(seat).bold(); Text(r.read).font(.caption).foregroundStyle(.secondary); Spacer(); AgeLabel(r.producedAt, now: now) }
                            Text(r.headline).font(.callout)
                            if !r.unavailable.isEmpty { Text("dark: \(r.unavailable.joined(separator: ", "))").font(.caption).foregroundStyle(DeskColor.fail) }
                        }
                    }
                    ForEach(required.subtracting(snap.reports.keys).sorted(), id: \.self) { seat in
                        HStack { Text(seat).bold(); Text("required · dark").font(.caption).foregroundStyle(DeskColor.fail); Spacer(); AgeLabel(nil, now: now) }
                    }
                    if snap.reports.isEmpty && required.isEmpty { Text("none yet").foregroundStyle(.secondary) }
                }
                Section(header: SectionHeader("Assignments")) {
                    if snap.assignments.isEmpty { Text("none yet").foregroundStyle(.secondary) }
                    ForEach(snap.assignments.keys.sorted(), id: \.self) { seat in
                        let a = snap.assignments[seat]!
                        VStack(alignment: .leading, spacing: 3) {
                            HStack { Text(seat).bold(); Spacer(); Pct(a.atStakePct); AgeLabel(a.issuedAt, now: now) }
                            Text("answered \(a.coverage.answered.count)/\(a.coverage.assigned)").font(.caption)
                            if !a.coverage.unanswered.isEmpty { Text("unanswered: \(a.coverage.unanswered.joined(separator: ", "))").font(.caption).foregroundStyle(.secondary) }
                        }
                    }
                }
            }
        }
        .refreshable { await store.refresh() }
    }
}
