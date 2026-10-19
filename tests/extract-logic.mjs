/**
 * The pure logic of barra.html (no DOM at all) lives between two markers inside
 * the <script>. This script extracts it to tests/logic.mjs so it can be tested
 * with Node without spinning up a browser.
 *
 * It is regenerated on every `make test`, so it never goes out of sync.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(here, '..', 'barra.html'), 'utf8');

const START = '// ==================== LOGIC START';
const END   = '// ==================== LOGIC END';
const a = html.indexOf(START);
const b = html.indexOf(END);
if (a < 0 || b < 0) throw new Error("Can't find the LOGIC START/END markers in barra.html");

const EXPORTS = [
  'MOVEMENTS', 'SEED_MAXES', 'HIST_MAXES', 'DEFAULT_PLATES', 'RM_SUBSTITUTE', 'effectiveRM',
  'norm', 'aliasIndex', 'findMovement', 'extractPercents', 'extractKilos',
  'extractSetsReps', 'extractInterval', 'extractRest',
  'splitComplex', 'governingMovement', 'governingFor', 'cleanLine', 'parseWod', 'parsePRs',
  'achievablePerSide', 'bestLoad', 'pctToKg', 'plateCount', 'ALIASES',
];

fs.writeFileSync(
  path.join(here, 'logic.mjs'),
  html.slice(a, b) + `\nexport {${EXPORTS.join(',')}};\n`
);
console.log('tests/logic.mjs regenerated from barra.html');
