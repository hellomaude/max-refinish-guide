// The app's state: one snapshot, when it was fetched, and the pairing.
// Refresh is polling, not push — the daemon's push goes to ntfy/Pushover,
// which reaches the phone regardless of whether this app is open.
import Foundation
import Observation

@MainActor
@Observable
public final class DeskStore {
    public private(set) var pairing: Pairing?
    public private(set) var snapshot: Snapshot?
    public private(set) var fetchedAt: Date?
    public private(set) var lastError: String?
    public private(set) var refreshing = false

    public let device: String

    public init(device: String) {
        self.device = device
        self.pairing = Keychain.load()
    }

    public var api: DeskAPI? { pairing.map { DeskAPI(pairing: $0) } }
    public var paired: Bool { pairing != nil }

    public func pair(with text: String) -> Bool {
        guard let p = Pairing.parse(text) else { return false }
        do { try Keychain.save(p) } catch { lastError = "Keychain: \(error)"; return false }
        pairing = p
        return true
    }

    public func unpair() {
        Keychain.clear()
        pairing = nil
        snapshot = nil
        fetchedAt = nil
    }

    public func refresh() async {
        guard let api else { lastError = DeskAPIError.notPaired.localizedDescription; return }
        refreshing = true
        defer { refreshing = false }
        do {
            snapshot = try await api.snapshot()
            fetchedAt = Date()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    /// Confirm exactly what is on screen. Returns the server's line.
    public func confirm(_ stamp: StampInfo, note: String = "") async -> Result<ConfirmResponse, DeskAPIError> {
        guard let api else { return .failure(.notPaired) }
        do {
            let r = try await api.confirm(ConfirmRequest(
                ticketId: stamp.ticketId, stampSha256: stamp.stampSha256, device: device, note: note))
            await refresh()
            return .success(r)
        } catch let e as DeskAPIError { return .failure(e) }
        catch { return .failure(.transport(error.localizedDescription)) }
    }

    /// Keep polling while a view is on screen.
    public func poll(every seconds: Double = 30) async {
        while !Task.isCancelled {
            await refresh()
            try? await Task.sleep(for: .seconds(seconds))
        }
    }
}
