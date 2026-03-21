/**
 * TC-06 – TC-13: canAct derivation logic (pure boolean)
 * Tests the logic: isMyTurn && isPlaying && handInProgress && connectionStatus === 'connected'
 */

// Mirror the derivation from [tableId].tsx
function deriveCanAct(
  currentActorId: string | null,
  yourUserId: string,
  myStatus: string | null,
  handInProgress: boolean,
  connectionStatus: string
): boolean {
  const isMyTurn = currentActorId === yourUserId;
  const isPlaying = myStatus === 'playing';
  return Boolean(isMyTurn && isPlaying && handInProgress && connectionStatus === 'connected');
}

describe('canAct derivation', () => {
  it('TC-06: true when all conditions met', () => {
    expect(deriveCanAct('u1', 'u1', 'playing', true, 'connected')).toBe(true);
  });

  it('TC-07: false when not my turn', () => {
    expect(deriveCanAct('u2', 'u1', 'playing', true, 'connected')).toBe(false);
  });

  it('TC-08: false when status is sit_out', () => {
    expect(deriveCanAct('u1', 'u1', 'sit_out', true, 'connected')).toBe(false);
  });

  it('TC-09: false when status is waiting', () => {
    expect(deriveCanAct('u1', 'u1', 'waiting', true, 'connected')).toBe(false);
  });

  it('TC-10: false when no hand in progress', () => {
    expect(deriveCanAct('u1', 'u1', 'playing', false, 'connected')).toBe(false);
  });

  it('TC-11: false when disconnected', () => {
    expect(deriveCanAct('u1', 'u1', 'playing', true, 'disconnected')).toBe(false);
  });

  it('TC-12: false when reconnecting', () => {
    expect(deriveCanAct('u1', 'u1', 'playing', true, 'reconnecting')).toBe(false);
  });

  it('TC-13: false when currentActorId is null', () => {
    expect(deriveCanAct(null, 'u1', 'playing', true, 'connected')).toBe(false);
  });
});
