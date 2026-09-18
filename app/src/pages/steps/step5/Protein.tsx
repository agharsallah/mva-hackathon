import type { Step5Domain, Step5Residue } from '../../../api/types';
import { C } from '../../../lib/palette';
import { tracksFor } from './metrics';

/** InterPro's own word for what an entry describes, shortened for a legend. */
const KIND: Record<string, string> = {
  domain: 'domain',
  homologous_superfamily: 'superfamily',
  family: 'family',
};

/**
 * One protein drawn as a rule, with its InterPro entries as bars and the missense allele
 * as a tick.
 *
 * **Nothing here is a coordinate.** Every position is a fraction of the protein's own
 * length, which is all the picture needs and all this repository is allowed to commit.
 *
 * **Colour carries the pre-registered test.** Only an entry InterPro types as a *domain*
 * counts for the claim; families and superfamilies span most of a protein and would make
 * the test pass for almost any residue, so they are drawn in machinery blue and excluded.
 * The tick is green when the residue falls inside a domain and red when it does not.
 */
export function ProteinTrack({
  residue,
  domains,
}: {
  residue: Step5Residue;
  domains: Step5Domain[];
}) {
  const tracks = tracksFor(domains, residue.gene);
  const length = tracks[0]?.protein_length ?? 0;
  const at = residue.fraction ?? 0;

  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs text-chrome-400">
        <span>
          <strong className="text-chrome-200">{residue.gene}</strong> · {residue.uniprot} ·{' '}
          {length.toLocaleString()} residues
        </span>
        <span>
          pLDDT {residue.plddt === null ? '—' : residue.plddt.toFixed(1)} ·{' '}
          {residue.am_class || 'no AlphaMissense class'}
        </span>
      </div>
      <svg
        viewBox="0 0 100 16"
        className="h-10 w-full"
        role="img"
        aria-label={`${residue.gene} domains`}
      >
        <rect x="0" y="7" width="100" height="2" fill={C.absent} />
        {tracks.map((track) => (
          <rect
            key={`${track.interpro}-${track.start_fraction}`}
            x={track.start_fraction * 100}
            y={track.entry_type === 'domain' ? 4 : 6}
            width={Math.max((track.end_fraction - track.start_fraction) * 100, 0.4)}
            height={track.entry_type === 'domain' ? 8 : 4}
            fill={track.entry_type === 'domain' ? C.decision : C.machinery}
            opacity={track.entry_type === 'domain' ? 0.95 : 0.55}
          >
            <title>
              {track.interpro} {track.domain_name} ({KIND[track.entry_type] ?? track.entry_type})
            </title>
          </rect>
        ))}
        {residue.fraction !== null && (
          <g>
            <rect
              x={Math.min(Math.max(at * 100 - 0.25, 0), 99.5)}
              y="1"
              width="0.5"
              height="14"
              fill={residue.in_domain ? C.good : C.broken}
            />
            <title>the missense allele, at {(at * 100).toFixed(1)}% along the protein</title>
          </g>
        )}
      </svg>
    </div>
  );
}
