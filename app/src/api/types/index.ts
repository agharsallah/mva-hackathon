/**
 * Types transcribed 1:1 from the viz API contract
 * (scratchpad/viz-api-contract.md). Service: mva-viz-api, FastAPI, 127.0.0.1:8900.
 *
 * Every endpoint answers with the same envelope, so the client can be one function:
 *   { data, cached_at, source }
 * `cached_at` is null for endpoints computed on the spot; `source` names the table,
 * object or file the rows came from (that string is the page's provenance line).
 *
 * One module per API domain — this file is only the barrel, so every importer keeps
 * writing `from '../api/types'` regardless of which domain a type lives in.
 */

export type * from './callset';
export type * from './catalog';
export type * from './clinvar';
export type * from './envelope';
export type * from './genome';
export type * from './health';
export type * from './jobs';
export type * from './overview';
export type * from './panel';
export type * from './phenotype';
export type * from './protein';
export type * from './provenance';
export type * from './reads';
export type * from './science';
export type * from './search';
export type * from './step1';
export type * from './steps';
export type * from './submissions';
export type * from './track2';
