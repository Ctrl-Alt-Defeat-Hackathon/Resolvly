import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="bg-background text-on-background selection:bg-secondary-container min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-grow pt-24 pb-12">
      {/* Hero Section */}
      <section className="pb-20 editorial-margin">
        <div className="grid lg:grid-cols-[1fr_400px] gap-16 items-center">
          <div className="space-y-8">
            <span className="inline-block px-3 py-1 bg-secondary-container text-on-secondary-container text-[10px] uppercase tracking-widest font-bold rounded-full">
              Indiana Regulatory Compliant
            </span>
            <h1 className="text-6xl font-extrabold text-primary leading-[1.1] tracking-tight">
              Understand your Indiana insurance denial in plain English.
            </h1>
            <p className="text-xl text-on-surface-variant max-w-2xl leading-relaxed">
              Helping Hoosiers navigate insurance denial complexity since 2026. Professional analysis, regulatory alignment, and guided appeal drafting.
            </p>
            <div className="flex flex-wrap gap-4 pt-4">
              <button
                onClick={() => navigate('/analyze')}
                className="px-8 py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2"
              >
                Start Free Analysis
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_forward</span>
              </button>
            </div>
          </div>

          <div className="relative group">
            <div className="absolute -inset-4 bg-primary-container/5 rounded-[2rem] blur-2xl group-hover:bg-primary-container/10 transition-all duration-500"></div>
            <div className="relative aspect-[4/5] bg-surface-container-low rounded-2xl overflow-hidden shadow-2xl border border-white/20">
              <img
                alt="Indiana Legal Document"
                className="w-full h-full object-cover grayscale mix-blend-multiply opacity-80"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuBOeuREEIsG_VJ8MueUkq0Qvqlr-K1U4FNIv5iQkV0n9FAHAmnEB9RKSUa4Cs0jTJT61qSeDL5sVGpLYVqPFgW-gLVHqecUSQuIrO1qNVrq5iXlK6tBk3sbKpkVBlAAdHjIneucNRSVLNTZsXSxZlfq0MCdGBGP4ohfvON2wamS-KjlnOZnYuyKrJccJzljUO0e7y8Ikby-yl3TAEzjDsGmvPKufDoBtTQVj8-7Oc6YfM2jXC5Ean-J6Tl7-UisNt2Mq7NqJr12kyQ"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-primary/40 to-transparent"></div>
              <div className="absolute bottom-6 left-6 right-6 p-6 bg-white/80 backdrop-blur-md rounded-xl border border-white/40">
                <div className="flex items-center gap-3 mb-2">
                  <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>verified</span>
                  <span className="text-xs font-bold text-primary uppercase tracking-wider">Indiana Accredited</span>
                </div>
                <p className="text-sm font-medium text-on-surface italic">
                  "Resolvly translated a 14-page clinical denial into a 3-step action plan in minutes."
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pipeline Section */}
      <section className="py-24 bg-surface-container-low">
        <div className="editorial-margin">
          <div className="mb-16">
            <h2 className="text-4xl font-extrabold text-primary mb-4 tracking-tight">Proprietary Resolution Pipeline</h2>
            <div className="w-24 h-1.5 bg-primary rounded-full"></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {[
              { icon: 'cloud_upload', title: 'Ingestion', desc: 'Secure document intake via multi-channel OCR and PDF parsing technology.', border: 'border-primary' },
              { icon: 'query_stats', title: 'Extraction', desc: 'Identifying policy numbers, clinical denial codes, and regulatory deadlines.', border: 'border-primary/60' },
              { icon: 'database', title: 'Enrichment', desc: 'Cross-referencing Indiana insurance laws and carrier-specific guidelines.', border: 'border-primary/40' },
              { icon: 'psychology', title: 'Analysis', desc: 'Pattern recognition for unfair claim settlement practices and logic gaps.', border: 'border-primary/20' },
            ].map(({ icon, title, desc, border }) => (
              <div key={title} className={`p-6 bg-surface-container-lowest rounded-xl shadow-sm hover:shadow-md transition-all border-l-4 ${border}`}>
                <span className="material-symbols-outlined text-primary mb-4 block" style={{ fontSize: 32 }}>{icon}</span>
                <h3 className="font-bold text-lg mb-2">{title}</h3>
                <p className="text-xs text-on-surface-variant leading-relaxed">{desc}</p>
              </div>
            ))}
            <div className="p-6 bg-primary text-on-primary rounded-xl shadow-lg lg:scale-105">
              <span className="material-symbols-outlined mb-4 block" style={{ fontSize: 32 }}>assignment_turned_in</span>
              <h3 className="font-bold text-lg mb-2">Output</h3>
              <ul className="space-y-3 mt-4">
                {[
                  { icon: 'picture_as_pdf', label: 'PDF export' },
                  { icon: 'calendar_month', label: '.ics calendar export' },
                  { icon: 'fact_check', label: 'Letter checker' },
                  { icon: 'notification_important', label: 'Deadline reminders' },
                ].map(({ icon, label }) => (
                  <li key={label} className="flex items-center gap-2 text-[10px] uppercase font-bold tracking-wider">
                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{icon}</span> {label}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Security & Compliance */}
      <section className="py-24 editorial-margin">
        <div className="grid md:grid-cols-2 gap-12">
          <div className="relative overflow-hidden rounded-[2rem] bg-surface-container-lowest p-12 border border-outline-variant/10 group">
            <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-secondary-container/30 rounded-full blur-3xl group-hover:bg-secondary-container/50 transition-colors"></div>
            <div className="relative">
              <div className="w-12 h-12 bg-primary flex items-center justify-center rounded-xl mb-6 shadow-md">
                <span className="material-symbols-outlined text-white">shield_lock</span>
              </div>
              <h3 className="text-2xl font-bold text-primary mb-4">Secured by Guardian-Grade Encryption</h3>
              <p className="text-on-surface-variant leading-relaxed mb-6">
                Your medical data is protected by AES-256 at-rest and TLS 1.3 in-transit encryption. We implement zero-knowledge protocols, ensuring that your sensitive clinical records remain private and accessible only by you.
              </p>
              <div className="flex items-center gap-4">
                <div className="flex flex-col">
                  <span className="text-[10px] font-bold uppercase text-outline tracking-tighter">Encryption Standard</span>
                  <span className="text-sm font-bold text-primary">Military Level 256-bit</span>
                </div>
                <div className="w-px h-8 bg-outline-variant/30"></div>
                <div className="flex flex-col">
                  <span className="text-[10px] font-bold uppercase text-outline tracking-tighter">Architecture</span>
                  <span className="text-sm font-bold text-primary">SOC2 Type II</span>
                </div>
              </div>
            </div>
          </div>

          <div className="relative overflow-hidden rounded-[2rem] bg-primary text-on-primary p-12 shadow-2xl group">
            <div className="absolute bottom-0 left-0 -ml-16 -mb-16 w-64 h-64 bg-white/5 rounded-full blur-3xl"></div>
            <div className="relative">
              <div className="w-12 h-12 bg-white flex items-center justify-center rounded-xl mb-6 shadow-md">
                <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>account_balance</span>
              </div>
              <h3 className="text-2xl font-bold mb-4">Indiana-First Compliance Architecture</h3>
              <p className="text-on-primary/80 leading-relaxed mb-6">
                Engineered specifically for the Indiana Department of Insurance (IDOI) regulatory framework. Our system updates in real-time with Indiana IC 27-4-1-4 Unfair Claim Settlement Practices and legislative amendments.
              </p>
              <div className="space-y-3">
                {['IDOI Rule 760 Alignment', 'Local Counsel Knowledge Graph', 'State-specific Deadline Tracking'].map(item => (
                  <div key={item} className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-secondary-fixed text-sm">check_circle</span>
                    <span className="text-sm font-medium">{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Indiana Visual Anchor */}
      <section className="py-12 editorial-margin">
        <div className="rounded-3xl overflow-hidden h-[400px] relative">
          <img
            alt="Indiana Landscape"
            className="w-full h-full object-cover grayscale"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuCHF1HIfyGRpKhBfvfFdhCaxYabE2H6xiP-Aui2uz_MOPfX0JUCHp8Ghqmo4RMP9q9CgSPLaMox4VWMVTfyDVusn50ngILBR23vgK_S5IMdyElilL5O4_vKiHEAUE3uyyeTgfHm5fHNEmbFIeGC0cvd-P-ZyrGpEGbDAz1JsV5c1Fb_s__ydyUmadxGyH2mlDibNn_Z_blY67_qirok0JM8004EWnYG_e-BhVwk_8fYKc3WTA9MIxuUI7d4F8EEbPtN3bIeBH_X1jY"
          />
          <div className="absolute inset-0 bg-primary/40 mix-blend-multiply"></div>
          <div className="absolute inset-0 flex items-center justify-center text-center p-8">
            <div className="max-w-2xl">
              <h2 className="text-4xl font-extrabold text-white mb-6">
                Empowering every Hoosier with the tools to push back.
              </h2>
              <button
                onClick={() => navigate('/analyze')}
                className="px-10 py-5 bg-white text-primary font-bold rounded-xl shadow-2xl hover:bg-surface-container-low transition-all"
              >
                Begin Your Appeal Analysis
              </button>
            </div>
          </div>
        </div>
      </section>
      </main>

      <Footer disclaimer="Legal Disclaimer: Resolvly is an advocacy software platform and does not constitute a law firm or medical provider. We do not provide legal advice or clinical diagnoses. Our analysis is based on provided documentation and publicly available Indiana Department of Insurance regulatory frameworks." />
    </div>
  )
}
