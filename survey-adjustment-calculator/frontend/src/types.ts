export type Point = { X: number; Y: number; Z: number; H: number; fixed: string[] }
export type Observation = { id: string; kind: string; points: string[]; value: string | number | number[] | null; sigma: string | number | number[]; covariance: string | number[][] | null; components: string[]; enabled: boolean }
export type Project = { format: 'survey-network-project'; version: 1; family: string; name: string; method: string; points: Record<string, Point>; observations: Observation[]; constraints: { terms: Record<string, number>; value: number }[] }
export type Stats = { n: number; t: number; r: number; parameters: number; constraints: number; defect: number; points: number; observations: number; solvable: boolean }
export type Matrix = number[] | number[][]
export type Analysis = { statistics: Stats; matrices: Record<string, Matrix>; parameter_order: string[]; observation_order: string[]; predicted: Record<string, number[]>; missing_observations: string[] }
export type Precision = { point: string; [key: string]: string | number }
export type Result = { n: number; t: number; r: number; dof: number; v: number[]; x: number[] | null; observed: number[] | null; adjusted: number[] | null; parameters: number[] | null; qxx: number[][] | null; qvv: number[][]; q_adjusted: number[][]; weighted_sum: number; posterior_sigma: number | null; precision_sigma: number | null; precision_source: string; equation_error: number; constraint_error: number; warnings: string[]; details: Record<string, Matrix>; std_adjusted?: number[]; std_v?: number[]; std_x?: number[]; report?: string }
export type Solution = { statistics: Stats; design: boolean; method: string; iterations: number; points: Record<string, Point>; parameter_order: string[]; observation_order: string[]; angular_rows: boolean[]; corrections: number[]; result: Result; matrices: Record<string, Matrix>; point_precision: Precision[]; relative_precision: { observation: string; sigma: number; quantity: string; length?: number; relative_denominator?: number }[]; report: string }
export type Draft = Record<string, string>
export type Bootstrap = { families: string[]; kinds: Record<string, string>; methods: Record<string, string>; formulas: Record<string, string>; examples: Record<string, Draft>; project: Project }
export type Selection = { type: 'point' | 'observation'; id: string } | null
export const axes = (family: string) => family === '水准网' ? ['H'] : family === 'GNSS网' ? ['X', 'Y', 'Z'] : ['X', 'Y']
export const kinds = (family: string) => family === '水准网' ? ['height', 'coordinate'] : family === 'GNSS网' ? ['gnss', 'coordinate'] : ['distance', 'angle', 'azimuth', 'coordinate']
export const number = (v: unknown, digits = 6): string => v === null || v === undefined ? '—' : typeof v === 'number' ? v === 0 ? '0' : Math.abs(v) < .00001 || Math.abs(v) >= 1e8 ? v.toExponential(4) : Number(v.toFixed(digits)).toString() : String(v)
export const values = (v: unknown) => Array.isArray(v) ? v.map(x => Array.isArray(x) ? x.map(y => number(y, 9)).join('  ') : number(x, 9)).join(Array.isArray(v[0]) ? '\n' : ', ') : v === null || v === undefined ? '' : String(v)
