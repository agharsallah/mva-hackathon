/**
 * Types transcribed 1:1 from the backend API contract.
 *
 * Every endpoint answers with the same envelope, so the client can be one function:
 *   { data, cached_at, source }
 * `cached_at` is null for endpoints computed on the spot; `source` names the table,
 * object or file the rows came from (that string is the page's provenance line).
 *
 * One module per API domain — this file is only the barrel, so every importer keeps
 * writing `from '../api/types'` regardless of which domain a type lives in.
 */

export type * from './envelope';
export type * from './health';
