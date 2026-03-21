function makeLogger(namespace: string) {
  return {
    log: (...args: unknown[]) => console.log(`[Zepo:${namespace}]`, ...args),
    warn: (...args: unknown[]) => console.warn(`[Zepo:${namespace}]`, ...args),
    error: (...args: unknown[]) => console.error(`[Zepo:${namespace}]`, ...args),
  };
}

export const AuthLogger = makeLogger('AuthStore');
export const ClubLogger = makeLogger('ClubStore');
export const TableLogger = makeLogger('TableStore');
export const SocketLogger = makeLogger('SocketClient');
