/*
 * Vendored by video from Archify 3.2.0
 * Source: https://github.com/tt-a1i/archify/blob/d6059331abbddb49bca380ff46dca8ce33158b04/archify/bin/delivery-update.mjs
 * Commit: d6059331abbddb49bca380ff46dca8ce33158b04
 * Licence: Apache-2.0; see NOTICE, LICENSE and LICENSE-MIT in this folder, and VENDORED.md.
 * Modified locally: yes. Each change sits between 'video MODIFIED begin' and
 * 'video MODIFIED end' markers and is listed in VENDORED.md.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const childPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'scripts', 'delivery-update-child.mjs');
const DEADLINE_MS = 1_000;
const MAX_OUTPUT_BYTES = 16 * 1_024;

function unavailable(reason) {
  return { status: 'unavailable', installedVersion: null, availableVersion: null,
    releaseNotes: null, checkedAt: null, source: null, noticeRequired: false,
    noticeText: null, reason };
}

function normalize(result) {
  if (result?.status === 'current') return {
    status: 'current', installedVersion: result.installedVersion,
    availableVersion: result.availableVersion, releaseNotes: null,
    checkedAt: result.checkedAt, source: result.source,
    noticeRequired: false, noticeText: null,
  };
  if (result?.status !== 'update_available') {
    return unavailable(result?.reason || (result?.status === 'silent' ? 'no-update' : 'invalid-result'));
  }
  const noticeRequired = result.noticeRequired !== false;
  const cached = result.source === 'cache';
  const noticeText = noticeRequired
    ? `Archify ${result.severity === 'security' ? 'security update' : 'update'}: ${result.installedVersion} → ${result.latestVersion}. ${cached
      ? `A previous check at ${result.checkedAt} found a newer release.`
      : 'A newer release is available.'} Release notes: ${result.releaseNotes}. Would you like me to update Archify?`
    : null;
  return {
    status: 'update_available',
    installedVersion: result.installedVersion,
    availableVersion: result.latestVersion,
    releaseNotes: result.releaseNotes,
    severity: result.severity,
    summary: result.summary ?? null,
    checkedAt: result.checkedAt,
    source: result.source,
    noticeRequired,
    noticeText,
    ...(result.eventKey ? { eventKey: result.eventKey } : {}),
    ...(result.reason ? { reason: result.reason } : {}),
    ...(result.suppressedUntil ? { suppressedUntil: result.suppressedUntil } : {}),
  };
}

// video MODIFIED begin — no update check: video makes no network request for Archify updates.
// Removed: spawning scripts/delivery-update-child.mjs, which fetched the update manifest.
export function startDeliveryUpdateCheck() {
  return Promise.resolve(unavailable('disabled'));
}
// video MODIFIED end
