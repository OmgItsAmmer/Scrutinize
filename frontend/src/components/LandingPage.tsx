import { EyeLogo } from "./EyeLogo";
import { VoiceMarquee } from "./landing/VoiceMarquee";
import { InfiniteGallery } from "./landing/InfiniteGallery";
import { useInertialScroll } from "./landing/useInertialScroll";
import { Reveal } from "./landing/Reveal";

type LandingPageProps = {
  onEnter: () => void;
};

const FILMSTRIP_FRAMES = [
  "linear-gradient(135deg, #f59e0b, #fbbf24)",
  "linear-gradient(135deg, #050505, #27272a)",
  "linear-gradient(135deg, #fbbf24, #f59e0b)",
  "linear-gradient(135deg, #27272a, #050505)",
  "linear-gradient(135deg, #f59e0b, #27272a)",
  "linear-gradient(135deg, #fbbf24, #050505)",
  "linear-gradient(135deg, #050505, #f59e0b)",
  "linear-gradient(135deg, #27272a, #fbbf24)",
];

export function LandingPage({ onEnter }: LandingPageProps) {
  useInertialScroll();

  return (
    <div className="scrutinize-landing">
      <style>{`
        .scrutinize-landing{
          --sl-image-accent: #8b5cf6;
          font-family: inherit;
          background: var(--app-bg);
          color: var(--app-text);
        }
        .scrutinize-landing *{box-sizing:border-box;}
        .scrutinize-landing h1,.scrutinize-landing h2,.scrutinize-landing h3{margin:0;letter-spacing:-0.02em;}
        .scrutinize-landing a{color:inherit;text-decoration:none;}
        .sl-page{max-width:1160px;margin:0 auto;padding:0 24px;width:100%;}

        .sl-glass{
          background: var(--app-bg-glass);
          border: 1px solid var(--app-border);
          backdrop-filter: blur(28px) saturate(180%);
          -webkit-backdrop-filter: blur(28px) saturate(180%);
          box-shadow: var(--app-shadow-soft), inset 0 1px 1px 0 rgba(255,255,255,0.84);
        }
        .sl-glass-strong{
          background: var(--app-bg-glass-strong);
          border: 1px solid var(--app-border);
          backdrop-filter: blur(32px) saturate(180%);
          -webkit-backdrop-filter: blur(32px) saturate(180%);
          box-shadow: var(--app-shadow), inset 0 1px 1.5px 0 rgba(255,255,255,0.95);
        }
        .sl-glass-dark{
          background: linear-gradient(160deg, rgba(5,5,5,0.9), rgba(20,20,24,0.86));
          border: 1px solid rgba(255,255,255,0.08);
          box-shadow: inset 0 1px 1px 0 rgba(255,255,255,0.06);
          color: #f5f5f7;
        }

        /* Nav — always fixed, outside the smooth-scroll layer */
        .sl-nav-wrap{position:fixed;top:14px;left:0;right:0;z-index:100;padding:0 24px;}
        .sl-nav{
          max-width:1160px;margin:0 auto;border-radius:9999px;padding:8px 10px 8px 18px;
          display:flex;align-items:center;justify-content:space-between;gap:24px;
        }
        .sl-nav .logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;color:var(--app-text);}
        .sl-nav .logo .eye-halo{filter: drop-shadow(0 4px 12px rgba(5,5,5,0.18));}
        .sl-nav nav{display:flex;gap:26px;font-size:14px;font-weight:600;color:var(--app-text-soft);}
        .sl-nav nav span{cursor:pointer;}
        .sl-nav nav span:hover{color:var(--app-text);}
        .sl-btn-primary{
          background: var(--app-primary);color: var(--app-primary-text);border:1px solid transparent;
          border-radius:9999px;padding:10px 20px;font-weight:600;font-size:14px;cursor:pointer;
          transition: background-color .18s ease, transform .18s ease;
        }
        .sl-btn-primary:hover{background:var(--app-primary-hover);transform:translateY(-1px);}
        .sl-btn-outline{
          background: var(--app-bg-glass-strong);color: var(--app-text);border:1px solid var(--app-border-strong);
          border-radius:9999px;padding:12px 22px;font-weight:600;font-size:14px;cursor:pointer;
          transition: background-color .18s ease, transform .18s ease;
        }
        .sl-btn-outline:hover{background:var(--app-bg-elevated);transform:translateY(-1px);}
        .sl-btn-outline.on-dark{background:rgba(255,255,255,0.08);color:#f5f5f7;border-color:rgba(255,255,255,0.18);}
        .sl-btn-outline.on-dark:hover{background:rgba(255,255,255,0.14);}

        /* Full-page sections */
        .sl-fullpage{
          min-height:100vh;min-height:100dvh;display:flex;flex-direction:column;justify-content:center;
          padding:140px 24px 96px;position:relative;
        }
        .sl-fullpage.compact{min-height:auto;padding:96px 24px;}
        .sl-fullpage.tint{background:var(--app-bg-soft);}

        .sl-eyebrow{
          display:inline-flex;align-items:center;gap:8px;font-size:12px;font-weight:700;
          letter-spacing:0.08em;text-transform:uppercase;padding:7px 14px;border-radius:9999px;
          color:var(--app-text-soft);margin-bottom:20px;
        }

        /* Hero */
        .sl-hero h1{font-size:clamp(42px,7.2vw,88px);line-height:1.02;font-weight:800;color:var(--app-text);text-align:center;}
        .sl-hero h1 .soft{color:var(--app-text-faint);font-weight:700;}
        .sl-hero p{
          font-size:19px;line-height:1.55;color:var(--app-text-muted);max-width:600px;margin:26px auto 0;text-align:center;
        }
        .sl-hero-actions{display:flex;gap:14px;justify-content:center;margin-top:36px;flex-wrap:wrap;}
        .sl-hero-marquee{margin-top:88px;max-width:900px;margin-left:auto;margin-right:auto;width:100%;}

        /* Featured chamber (full bleed dark) */
        .sl-chamber-grid{display:grid;grid-template-columns:1.1fr 0.9fr;gap:56px;align-items:center;max-width:1160px;margin:0 auto;}
        @media(max-width:900px){.sl-chamber-grid{grid-template-columns:1fr;}}
        .sl-chamber h2{color:#f5f5f7;font-size:clamp(32px,4.6vw,58px);font-weight:800;}
        .sl-chamber p{font-size:17px;color:rgba(245,245,247,0.75);max-width:480px;margin-top:16px;line-height:1.55;}

        .sl-mock{border-radius:28px;padding:22px;max-width:360px;margin:0 auto;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);}
        .sl-mock .bubble{
          background:rgba(255,255,255,0.08);color:#f5f5f7;border-radius:16px;padding:14px 16px;font-size:14px;
          margin-bottom:12px;line-height:1.4;border:1px solid rgba(255,255,255,0.06);
        }
        .sl-mock .bubble.q{background:rgba(14,165,233,0.16);border-color:rgba(14,165,233,0.3);}
        .sl-mock .cite{
          display:inline-block;background:rgba(16,185,129,0.9);color:#04140f;font-size:11px;font-weight:700;
          padding:2px 8px;border-radius:9999px;margin-left:6px;
        }

        /* Modality full sections */
        .sl-modality-grid{display:grid;grid-template-columns:0.85fr 1.15fr;gap:64px;align-items:center;max-width:1160px;margin:0 auto;width:100%;}
        @media(max-width:940px){.sl-modality-grid{grid-template-columns:1fr;gap:40px;}}
        .sl-modality-grid.reverse{grid-template-columns:1.15fr 0.85fr;}
        @media(max-width:940px){.sl-modality-grid.reverse{grid-template-columns:1fr;}}
        .sl-modality-icon{
          width:52px;height:52px;border-radius:9999px;display:flex;align-items:center;justify-content:center;
          color:#ffffff;flex:0 0 auto;margin-bottom:22px;
        }
        .sl-modality h2{font-size:clamp(32px,4.4vw,56px);font-weight:800;color:var(--app-text);margin:0 0 14px;}
        .sl-modality p.punch{font-size:20px;font-weight:600;color:var(--app-text);margin:0 0 12px;line-height:1.35;}
        .sl-modality p.desc{font-size:16px;line-height:1.6;color:var(--app-text-muted);max-width:480px;margin:0;}
        .sl-tags{display:flex;gap:8px;margin-top:20px;flex-wrap:wrap;}
        .sl-tag{
          background: var(--app-bg-glass-strong);border:1px solid var(--app-border-strong);
          color:var(--app-text-soft);font-size:12px;font-weight:600;padding:6px 12px;border-radius:9999px;
        }

        /* Text mock */
        .sl-text-lines{display:flex;flex-direction:column;gap:12px;padding:32px;border-radius:24px;}
        .sl-text-line{height:14px;border-radius:9999px;background:var(--app-border-strong);}
        .sl-text-line.cited{background: color-mix(in srgb, #0ea5e9 30%, var(--app-bg-glass-strong));}
        .sl-cite-chip{
          display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:700;color:#0369a1;
          background:rgba(14,165,233,0.14);border:1px solid rgba(14,165,233,0.3);padding:4px 10px;border-radius:9999px;
          margin-top:14px;
        }

        /* Filmstrip (video) */
        .sl-filmstrip{display:flex;gap:8px;padding:18px;border-radius:24px;overflow-x:auto;}
        .sl-filmstrip .frame{flex:0 0 110px;height:74px;border-radius:12px;position:relative;}
        .sl-filmstrip .frame.active{outline:2px solid #f59e0b;outline-offset:2px;}
        .sl-filmstrip .frame .ts{position:absolute;bottom:6px;right:8px;font-size:10px;color:rgba(255,255,255,0.9);font-weight:700;}

        .sl-gallery-frame{height:min(58vh,520px);border-radius:32px;overflow:hidden;position:relative;}
        .sl-gallery-hint{
          position:absolute;bottom:18px;left:50%;transform:translateX(-50%);z-index:5;
          font-size:12px;font-weight:600;color:var(--app-text-soft);padding:6px 14px;border-radius:9999px;pointer-events:none;
        }

        /* Strengths */
        .sl-card-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-top:44px;}
        @media(max-width:900px){.sl-card-grid{grid-template-columns:1fr;}}
        .sl-card{border-radius:28px;padding:30px;}
        .sl-card .icon-badge{
          width:44px;height:44px;border-radius:9999px;background:var(--app-primary);color:var(--app-primary-text);
          display:flex;align-items:center;justify-content:center;margin-bottom:18px;
        }
        .sl-card h4{font-size:19px;font-weight:700;margin-bottom:8px;color:var(--app-text);}
        .sl-card p{font-size:14px;line-height:1.55;color:var(--app-text-muted);margin:0;}

        /* Timeline */
        .sl-timeline{margin-top:36px;}
        .sl-timeline-row{display:flex;gap:24px;padding:22px 0;border-top:1px solid var(--app-border-strong);}
        .sl-timeline-row .date{flex:0 0 140px;font-size:13px;font-weight:700;color:var(--app-text-faint);}
        .sl-timeline-row h4{font-size:17px;font-weight:700;margin:0 0 4px;color:var(--app-text);}
        .sl-timeline-row p{font-size:14px;color:var(--app-text-muted);margin:0;}

        /* Footer */
        .sl-footer-top{
          max-width:1160px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;
          gap:32px;flex-wrap:wrap;width:100%;
        }
        .sl-footer h2{color:#f5f5f7;font-size:clamp(32px,4.8vw,58px);font-weight:800;max-width:560px;}
        .sl-footer-line{
          text-align:center;font-size:13px;color:rgba(245,245,247,0.5);margin-top:56px;max-width:1160px;
          margin-left:auto;margin-right:auto;padding-top:24px;border-top:1px solid rgba(255,255,255,0.08);width:100%;
        }

        @media(max-width:640px){
          .sl-fullpage{padding:120px 20px 64px;}
          .sl-hero-marquee{margin-top:56px;}
        }
      `}</style>

      {/* Nav — fixed overlay, always visible regardless of scroll position */}
      <div className="sl-nav-wrap">
        <div className="sl-nav sl-glass-strong">
          <div className="logo">
            <span className="eye-halo"><EyeLogo size={30} gap={5} /></span>
            Scrutinize
          </div>
          <nav>
            <span>Product</span><span>Modalities</span><span>Docs</span>
          </nav>
          <button className="sl-btn-primary" onClick={onEnter}>Sign In</button>
        </div>
      </div>

      <>
        {/* Hero — full viewport */}
        <section className="sl-fullpage sl-hero">
          <div className="sl-page">
            <h1>
              Search with <span className="soft">an eye</span><br />for detail
            </h1>
            <p>
              A unified ingestion and retrieval system that obsesses over the tiny details that
              make an answer trustworthy. Upload any modality, ask a question in plain language,
              and get a cited, grounded answer traced back to its source.
            </p>
            <div className="sl-hero-actions">
              <button className="sl-btn-primary" style={{ padding: "14px 26px", fontSize: 15 }} onClick={onEnter}>
                Get Started
              </button>
              <button className="sl-btn-outline" onClick={onEnter}>See how it works</button>
            </div>
            <div className="sl-hero-marquee">
              <VoiceMarquee />
            </div>
          </div>
        </section>

        {/* Featured capability — full-bleed dark chamber */}
        <Reveal>
          <section className="sl-fullpage compact sl-glass-dark">
            <div className="sl-chamber-grid">
              <div>
                <div
                  className="sl-eyebrow"
                  style={{ background: "rgba(16,185,129,0.16)", color: "#34d399", border: "1px solid rgba(16,185,129,0.3)" }}
                >
                  Featured capability
                </div>
                <h2>Grounded answers you can trust</h2>
                <p>
                  Ask a question across your uploaded library and get an answer with inline
                  citations pointing to the exact timestamp, page, or transcript line it came from.
                </p>
                <div className="sl-tags" style={{ marginTop: 24 }}>
                  <span className="sl-tag" style={{ background: "rgba(255,255,255,0.08)", borderColor: "rgba(255,255,255,0.14)", color: "#f5f5f7" }}>RAG</span>
                  <span className="sl-tag" style={{ background: "rgba(255,255,255,0.08)", borderColor: "rgba(255,255,255,0.14)", color: "#f5f5f7" }}>Multimodal</span>
                  <span className="sl-tag" style={{ background: "rgba(255,255,255,0.08)", borderColor: "rgba(255,255,255,0.14)", color: "#f5f5f7" }}>Cited</span>
                </div>
                <button className="sl-btn-outline on-dark" style={{ marginTop: 28 }} onClick={onEnter}>
                  Try it now
                </button>
              </div>
              <div className="sl-mock">
                <div className="bubble q">What did the Q3 earnings call say about margins?</div>
                <div className="bubble">
                  Gross margin expanded 2.1pts YoY, driven by supply-chain costs.
                  <span className="cite">source · 14:22</span>
                </div>
              </div>
            </div>
          </section>
        </Reveal>

        {/* Text — full page */}
        <Reveal>
          <section className="sl-fullpage tint">
            <div className="sl-modality-grid">
              <div>
                <div className="sl-modality-icon" style={{ background: "#0ea5e9" }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6" />
                    <path d="M8 13h8M8 17h5" />
                  </svg>
                </div>
                <h2>Text</h2>
                <p className="punch">Turn a thousand pages into one honest answer.</p>
                <p className="desc">
                  PDFs, notes, and articles are chunked and embedded for semantic search, so every
                  paragraph becomes a citation waiting to happen.
                </p>
                <div className="sl-tags"><span className="sl-tag">Chunking</span><span className="sl-tag">Embeddings</span><span className="sl-tag">RAG</span></div>
              </div>
              <div className="sl-text-lines sl-glass-strong">
                <div className="sl-text-line" style={{ width: "88%" }} />
                <div className="sl-text-line" style={{ width: "94%" }} />
                <div className="sl-text-line cited" style={{ width: "76%" }} />
                <div className="sl-text-line" style={{ width: "82%" }} />
                <div className="sl-text-line" style={{ width: "60%" }} />
                <span className="sl-cite-chip">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}><path d="M20 6L9 17l-5-5" /></svg>
                  cited · p.4, ¶2
                </span>
              </div>
            </div>
          </section>
        </Reveal>

        {/* Audio — full page, the voice marquee is the demo */}
        <Reveal>
          <section className="sl-fullpage">
            <div className="sl-page">
              <div className="sl-modality-icon" style={{ background: "#10b981" }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
                  <path d="M19 10v2a7 7 0 01-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              </div>
              <h2>Audio</h2>
              <p className="punch">If it was said out loud, we can prove it.</p>
              <p className="desc">
                Automatic transcription with timestamp-level citation support — every word spoken
                becomes searchable text, permanently traceable back to the moment it was said.
              </p>
              <div className="sl-tags"><span className="sl-tag">Transcription</span><span className="sl-tag">ASR</span><span className="sl-tag">Timestamps</span></div>
              <div style={{ marginTop: 56, maxWidth: 760 }}>
                <VoiceMarquee
                  text="the meeting ran twelve minutes over, and everyone agreed to revisit the roadmap next Tuesday"
                  accent="#10b981"
                />
              </div>
            </div>
          </section>
        </Reveal>

        {/* Images — full page, infinite canvas */}
        <Reveal>
          <section className="sl-fullpage tint">
            <div className="sl-modality-grid reverse">
              <div className="sl-gallery-frame sl-glass-strong">
                <InfiniteGallery density={4} imageWidth={150} imageHeight={150} rounded={10} />
                <span className="sl-gallery-hint sl-glass">Drag to pan · scroll to zoom — infinitely</span>
              </div>
              <div>
                <div className="sl-modality-icon" style={{ background: "#8b5cf6" }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="9" cy="9" r="2" /><path d="M21 15l-5-5L5 21" />
                  </svg>
                </div>
                <h2>Images</h2>
                <p className="punch">Every image lives on one infinite canvas.</p>
                <p className="desc">
                  Visual search across your entire image library — drag, scroll, and zoom without
                  limit until you find the exact frame you're after.
                </p>
                <div className="sl-tags"><span className="sl-tag">Visual search</span><span className="sl-tag">Infinite canvas</span></div>
              </div>
            </div>
          </section>
        </Reveal>

        {/* Video — full page */}
        <Reveal>
          <section className="sl-fullpage">
            <div className="sl-modality-grid">
              <div>
                <div className="sl-modality-icon" style={{ background: "#f59e0b" }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M23 7l-7 5 7 5V7z" /><rect x="1" y="5" width="15" height="14" rx="2" />
                  </svg>
                </div>
                <h2>Video</h2>
                <p className="punch">Skip the scrubbing. Search the scene.</p>
                <p className="desc">
                  Frame and speech understanding, searchable alongside your other sources — jump
                  straight to the moment, not the whole file.
                </p>
                <div className="sl-tags"><span className="sl-tag">Frame search</span><span className="sl-tag">Speech + vision</span></div>
              </div>
              <div className="sl-filmstrip sl-glass-strong">
                {FILMSTRIP_FRAMES.map((bg, i) => (
                  <div key={i} className={`frame${i === 3 ? " active" : ""}`} style={{ background: bg }}>
                    <span className="ts">{`0:0${i}`}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </Reveal>

        {/* Strengths */}
        <Reveal>
          <section className="sl-fullpage compact tint">
            <div className="sl-page">
              <div className="sl-eyebrow sl-glass">Why Scrutinize</div>
              <h2 style={{ fontSize: "clamp(30px,4vw,48px)", fontWeight: 800 }}>Strengths &amp; principles</h2>
              <div className="sl-card-grid">
                <div className="sl-card sl-glass">
                  <div className="icon-badge"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/></svg></div>
                  <h4>Unified Retrieval</h4>
                  <p>One search index across text, audio, images, and video — no separate silos to query.</p>
                </div>
                <div className="sl-card sl-glass">
                  <div className="icon-badge"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg></div>
                  <h4>Groundedness First</h4>
                  <p>Every answer is checked against its cited source before it reaches you.</p>
                </div>
                <div className="sl-card sl-glass">
                  <div className="icon-badge"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M10 13a5 5 0 007.07 0l1.41-1.41a5 5 0 00-7.07-7.07L10 6"/><path d="M14 11a5 5 0 00-7.07 0L5.5 12.4a5 5 0 007.07 7.07L14 18"/></svg></div>
                  <h4>Built for Research</h4>
                  <p>Designed for teams that need to verify, not just summarize.</p>
                </div>
              </div>
            </div>
          </section>
        </Reveal>

        {/* About / timeline */}
        <Reveal>
          <section className="sl-fullpage compact">
            <div className="sl-page">
              <div className="sl-eyebrow sl-glass">About</div>
              <h2 style={{ fontSize: "clamp(30px,4vw,48px)", fontWeight: 800 }}>A little more about Scrutinize</h2>
              <p style={{ fontSize: 17, lineHeight: 1.6, color: "var(--app-text-muted)", maxWidth: 620, marginTop: 18 }}>
                Scrutinize started as an ingestion pipeline for a single modality before growing
                into a unified system that treats text, audio, images, and video as equal citizens
                of the same search index. The name is the mission: every answer gets scrutinized
                against its source before it's shown to you.
              </p>
              <div className="sl-timeline">
                <div className="sl-timeline-row">
                  <div className="date">Phase 3 — Now</div>
                  <div><h4>Burr orchestration &amp; evidence assessment</h4><p>Multi-agent pipeline verifies citations before answers are returned.</p></div>
                </div>
                <div className="sl-timeline-row">
                  <div className="date">Phase 2</div>
                  <div><h4>RRF retrieval &amp; RAG synthesis</h4><p>Hybrid keyword + vector retrieval across all modalities.</p></div>
                </div>
                <div className="sl-timeline-row">
                  <div className="date">Phase 1</div>
                  <div><h4>Ingestion pipeline</h4><p>Multimodal upload, chunking, and embedding foundation.</p></div>
                </div>
              </div>
            </div>
          </section>
        </Reveal>

        {/* Footer / CTA */}
        <Reveal>
          <footer className="sl-fullpage compact sl-glass-dark">
            <div className="sl-footer-top">
              <div>
                <div
                  className="sl-eyebrow"
                  style={{ background: "rgba(16,185,129,0.16)", color: "#34d399", border: "1px solid rgba(16,185,129,0.3)" }}
                >
                  Get started
                </div>
                <h2>Let's scrutinize your sources.</h2>
              </div>
              <button className="sl-btn-primary" style={{ padding: "14px 26px", fontSize: 15 }} onClick={onEnter}>
                Sign In
              </button>
            </div>
            <div className="sl-footer-line">Scrutinize — unified retrieval across text, audio, images, and video.</div>
          </footer>
        </Reveal>
      </>
    </div>
  );
}
