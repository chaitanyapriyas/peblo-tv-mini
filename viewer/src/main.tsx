import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
type Artwork = Record<string, string>;
type E = {
  episode_number: number;
  title: string;
  duration_seconds: number;
  languages: string[];
  artwork?: Artwork;
};
type S = { season_number: number; episodes: E[] };
type Show = {
  show_id: string;
  title: string;
  description: string;
  category: string;
  section: string;
  artwork?: Artwork;
  seasons: S[];
};
const asset = (key?: string) => (key ? `${API}/media/${key}` : undefined);
function App() {
  const [shows, setShows] = useState<Show[]>([]),
    [q, setQ] = useState(""),
    [selected, setSelected] = useState<Show>(),
    [language, setLanguage] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    fetch(API + "/catalog")
      .then((r) =>
        r.ok ? r.json() : Promise.reject(Error("No published catalogue yet")),
      )
      .then((x) => setShows(x.shows))
      .catch((e) => setError(e.message));
  }, []);
  const visible = shows.filter((s) =>
      (s.title + " " + s.description + " " + s.category)
        .toLowerCase()
        .includes(q.toLowerCase()),
    ),
    hero = visible[0];
  return (
    <main>
      <header>
        <b>
          PEBLO<span>TV</span>
        </b>
        <input
          placeholder="Search titles, categories"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <small>PUBLIC</small>
      </header>
      {error ? (
        <section className="empty">
          <h1>Catalogue offline</h1>
          <p>{error}</p>
        </section>
      ) : (
        hero && (
          <>
            <section
              className="hero"
              style={{
                backgroundImage: hero.artwork?.banner
                  ? `linear-gradient(90deg,rgba(15,20,18,.95),rgba(15,20,18,.3)),url(${asset(hero.artwork.banner)})`
                  : undefined,
              }}
            >
              <small>{hero.category.toUpperCase()}</small>
              <h1>{hero.title}</h1>
              <p>{hero.description}</p>
              <button onClick={() => setSelected(hero)}>View show</button>
            </section>
            <section className="content">
              {[...new Set(visible.map((s) => s.section))].map((sec) => (
                <div key={sec}>
                  <h2>{sec.replaceAll("-", " ")}</h2>
                  <div className="tiles">
                    {visible
                      .filter((s) => s.section === sec)
                      .map((s) => (
                        <button
                          key={s.show_id}
                          className="tile"
                          onClick={() => setSelected(s)}
                        >
                          {(s.artwork?.poster || s.artwork?.banner) && (
                            <img
                              crossOrigin="anonymous"
                              src={asset(s.artwork.poster || s.artwork.banner)}
                              alt=""
                            />
                          )}
                          <span>{s.title}</span>
                          <small>{s.category}</small>
                        </button>
                      ))}
                  </div>
                </div>
              ))}
            </section>
          </>
        )
      )}
      {selected && (
        <aside>
          <button onClick={() => setSelected(undefined)}>Close</button>
          <h1>{selected.title}</h1>
          <p>{selected.description}</p>
          {[
            ...new Set(
              selected.seasons.flatMap((s) =>
                s.episodes.flatMap((e) => e.languages),
              ),
            ),
          ].map((code) => (
            <button
              key={code}
              className={
                language === code ? "language active-language" : "language"
              }
              onClick={() => setLanguage(code)}
            >
              {code.toUpperCase()}
            </button>
          ))}
          {selected.seasons.map((s) => (
            <section key={s.season_number}>
              <h2>Season {s.season_number}</h2>
              {s.episodes
                .filter((e) => !language || e.languages.includes(language))
                .map((e) => (
                  <div className="episode" key={e.episode_number}>
                    {e.artwork?.thumbnail && (
                      <img
                        crossOrigin="anonymous"
                        src={asset(e.artwork.thumbnail)}
                        alt=""
                      />
                    )}
                    <span>
                      {e.episode_number}. {e.title}
                    </span>
                    <small>
                      {Math.round(e.duration_seconds / 60)} min |{" "}
                      {e.languages.join(", ")}
                    </small>
                  </div>
                ))}
            </section>
          ))}
        </aside>
      )}
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
