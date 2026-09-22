// The book: every stamp, why, and the one control that matters.
import SwiftUI
import DeskKit

public struct BookView: View {
    @Bindable var store: DeskStore
    @State private var confirming: StampInfo?
    let now: Date

    public init(store: DeskStore, now: Date = Date()) { self.store = store; self.now = now }

    public var body: some View {
        List {
            if let snap = store.snapshot {
                Section {
                    LiveBanner(snap.mode.liveVenues)
                    HStack {
                        Text("\(snap.mode.mode) · \(snap.mode.execution)").font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Text(String(format: "%.2f%% of %.2f%%", snap.stamp.portfolioAllowedPct, snap.stamp.portfolioCapPct))
                            .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("stamped").font(.caption).foregroundStyle(.secondary)
                        AgeLabel(snap.stamp.stampedAt, now: now)
                        Spacer()
                        Text("fetched").font(.caption).foregroundStyle(.secondary)
                        AgeLabel(store.fetchedAt, now: now)
                    }
                }
                Section(header: SectionHeader("Book")) {
                    ForEach(snap.stamp.stamps) { stamp in
                        StampRow(stamp: stamp, confirmation: snap.confirmations[stamp.ticketId]) {
                            confirming = stamp
                        }
                    }
                }
                if !snap.health.darkSeats.isEmpty {
                    Section(header: SectionHeader("Dark dependencies")) {
                        ForEach(snap.health.darkSeats, id: \.self) { Text($0).font(.caption).foregroundStyle(DeskColor.fail) }
                    }
                }
            } else {
                Section { Text(store.lastError ?? "Loading…").foregroundStyle(.secondary) }
            }
        }
        .refreshable { await store.refresh() }
        .task { await store.poll() }
        .sheet(item: $confirming) { stamp in
            ConfirmSheet(store: store, stamp: stamp, jev: nil)
        }
    }
}

struct StampRow: View {
    let stamp: StampInfo
    let confirmation: ConfirmationInfo?
    let onConfirm: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(stamp.ticketId).font(.body.monospaced())
                Text(stamp.verdict.uppercased()).font(.caption.bold()).foregroundStyle(DeskColor.verdict(stamp.verdict))
                if !stamp.challengeVerdict.isEmpty {
                    Text("Jev \(stamp.challengeVerdict)").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Pct(stamp.allowedPct, bold: true)
            }
            Text(stamp.bindingConstraint).font(.caption).foregroundStyle(.secondary)
            if !stamp.reasons.isEmpty || !stamp.staleEvidence.isEmpty {
                DisclosureGroup("why") {
                    ForEach(stamp.reasons + stamp.staleEvidence.map { "stale: \($0)" }, id: \.self) {
                        Text($0).font(.caption).foregroundStyle(.secondary)
                    }
                }.font(.caption)
            }
            HStack {
                Spacer()
                if let c = confirmation, c.usable {
                    Label("confirmed · \(c.device)", systemImage: "checkmark.seal.fill")
                        .font(.caption).foregroundStyle(DeskColor.pass)
                } else {
                    Button(action: onConfirm) { Text(stamp.confirmable ? "Confirm…" : "—") }
                        .disabled(!stamp.confirmable)
                        .buttonStyle(.bordered)
                        .tint(DeskColor.accent)
                }
            }
        }
        .padding(.vertical, 4)
    }
}
