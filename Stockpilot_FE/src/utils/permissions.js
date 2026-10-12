// UI-only mirror of the server's role matrix, used to hide controls a role can't use.
// The API enforces these rules regardless - this is purely for a tidy interface.

const STAFF = new Set([
  'product:read',
  'inventory:read',
  'inventory:adjust',
  'order:read',
  'order:create',
  'order:update',
]);

export function can(role, permission) {
  if (role === 'OWNER') return true;
  if (role === 'STAFF') return STAFF.has(permission);
  return false;
}
