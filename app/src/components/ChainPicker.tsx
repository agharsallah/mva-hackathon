import type { Chain, ChainEdge, ChainView } from '../lib/lineageChains';
import { ALL_CHAINS } from '../lib/lineageChains';
import { Select } from './Controls';

/** `it4 · 68 recorded + 3 walked`, or `transfer.BLM (second case) · 95 recorded`. */
function label<E extends ChainEdge>(chain: Chain<E>): string {
  const walked = chain.edges.length - chain.own;
  const name = chain.transfer ? `${chain.id} (another case)` : chain.id;
  return `${name} · ${chain.own} recorded${walked > 0 ? ` + ${walked} walked back` : ''}`;
}

/**
 * The chain picker above a large lineage diagram. Renders nothing for a lineage small
 * enough to draw whole, so a short chain keeps its one diagram and no extra control.
 */
export function ChainPicker<E extends ChainEdge>({
  view,
  total,
}: {
  view: ChainView<E>;
  total: number;
}) {
  if (view.chains.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-3" data-testid="chain-picker">
      <Select
        label="chain"
        value={view.picked}
        options={[
          ...view.chains.map((c) => ({ value: c.id, label: label(c) })),
          { value: ALL_CHAINS, label: `every chain · ${total} edges` },
        ]}
        onChange={view.setPicked}
      />
      <span className="text-micro text-chrome-400">
        {total} recorded edges are too many for one diagram, so they are split by the table name
        each edge writes — one chain per prefix, each drawn down to its roots.
      </span>
    </div>
  );
}
