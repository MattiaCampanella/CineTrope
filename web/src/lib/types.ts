export type Card = {
  id: string;
  title: string;
  year: string | null;
  genres: string[];
  directors: string[];
  tropeCount: number;
  classes: string[];
  poster: string | null;
  backdrop: string | null;
};
export type Person = { id: string; label: string; photo: string | null };
export type Item = { id: string; label: string; sources?: unknown };
export type SharedItem = { id: string; label: string; sources: string[] };
export type Derived = { relation: string; via: string; via_id: string; rule: string };
export type Film = {
  id: string; title: string; year: string | null; type: string;
  directors: Person[]; actors: Person[]; genres: Item[]; tropes: Item[];
  poster: string | null; backdrop: string | null; classes: string[]; is_mindbender: boolean;
};
export type Rec = Card & {
  score: number;
  shared_tropes: Item[]; shared_directors: Item[]; shared_actors: Item[]; shared_genres: Item[];
  shared_tropes_count: number; shared_directors_count: number; shared_actors_count: number; shared_genres_count: number;
  source_summary: Record<string, number>;
};
export type Home = {
  hero: Card;
  rows: { id: string; title: string; items: Card[] }[];
  stats: Record<string, number>;
};
export type FilmPage = { film: Film; recommendations: Rec[]; priority: string };
export type Relation = {
  derived: Derived[];
  shared: Record<string, SharedItem[]>;
};
export type Explanation = {
  nodes: { id: string; label: string; group: string }[];
  edges: { id: string; from: string; to: string; label: string }[];
  node_count: number; edge_count: number; triple_count: number;
};
