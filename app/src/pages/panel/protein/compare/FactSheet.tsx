/**
 * One gene's fact sheet: the `StructureMetrics` row rendered as a `<dl>`, so the two columns
 * of the comparison read as two instances of the same form rather than two prose paragraphs.
 *
 * Every `null` in the metrics row renders as a *word*, never as a blank or a zero — that is
 * the whole reason this file exists rather than a `{value}` template. "not annotated" and
 * "0 %" are different claims, and so are "outside the annotated panel" and "no alleles".
 */

import { Link } from 'react-router-dom';

import { Badge } from '../../../../components/Badge';
import { FieldList } from '../../../../components/FieldList';
import { dec, int } from '../../../../lib/format';
import { angstromLabel } from '../distances';
import { GROUP_SHORT } from '../geneSet';
import type { StructureMetrics } from './metrics';

/** A fraction as a percentage, or the reason there is no number. */
const share = (value: number | null, absent: string): string =>
  value === null ? absent : `${dec(value * 100, 1)} %`;

export function FactSheet({ metrics }: { metrics: StructureMetrics }) {
  const alleles =
    metrics.allelesPlaced === null
      ? 'n/a — outside the annotated panel, so no allele was ever called here'
      : `${int(metrics.allelesPlaced)} placed, ${int(metrics.allelesUnplaced)} unplaced`;

  return (
    <FieldList
      labelWidth={132}
      fields={[
        {
          key: 'group',
          label: 'group',
          value: (
            <Badge tone={metrics.inPanel ? 'good' : 'machinery'}>
              {GROUP_SHORT[metrics.group]}
              {metrics.inPanel ? ' · alleles painted' : ' · fold only'}
            </Badge>
          ),
        },
        {
          key: 'residues',
          label: 'residues modelled',
          // The "and the rest is unmeasured" clause only when there *is* a rest: a fully
          // modelled chain that says residues carry no coordinates reads as a defect.
          value: `${int(metrics.modelled)} of ${int(metrics.length)} (${share(
            metrics.modelledFraction,
            'unknown length',
          )})${
            metrics.length > metrics.modelled
              ? `; the other ${int(metrics.length - metrics.modelled)} carry no coordinates and are unmeasured`
              : ' — the whole chain'
          }`,
        },
        {
          key: 'plddt',
          label: 'pLDDT ≥ 70',
          value: share(
            metrics.confidentFraction,
            'not reported — an experimental structure has no pLDDT column',
          ),
        },
        {
          key: 'secondary',
          label: 'helix / strand',
          value: `${share(metrics.helixFraction, 'not annotated')} / ${share(
            metrics.strandFraction,
            'not annotated',
          )} of the chain`,
        },
        {
          key: 'domains',
          label: `domains (${metrics.domains.length})`,
          value: metrics.domains.length === 0 ? 'none annotated' : metrics.domains.join(' · '),
        },
        { key: 'alleles', label: 'alleles', value: alleles },
        {
          key: 'closest',
          label: 'closest pair',
          value:
            metrics.closestPairAngstrom === null
              ? metrics.inPanel
                ? 'fewer than two alleles landed on a modelled residue'
                : 'n/a — fold only'
              : `${angstromLabel(metrics.closestPairAngstrom)} Cα${
                  metrics.closestPairConfident ? '' : ' — one end below pLDDT 70, not quotable'
                }`,
        },
        {
          key: 'provenance',
          label: 'provenance',
          value: (
            <>
              {`${
                metrics.provenance === 'alphafold'
                  ? 'AlphaFold — a prediction'
                  : 'PDB — an experiment'
              }${metrics.version ? ` · version ${metrics.version}` : ''}${
                metrics.uniprot ? ` · UniProt ${metrics.uniprot}` : ''
              } · translation ${metrics.protein}`}{' '}
              ·{' '}
              <Link
                to="/provenance#reference"
                className="text-machinery-400 underline decoration-dotted hover:text-machinery-300"
              >
                provenance manifest
              </Link>
            </>
          ),
        },
      ]}
    />
  );
}
