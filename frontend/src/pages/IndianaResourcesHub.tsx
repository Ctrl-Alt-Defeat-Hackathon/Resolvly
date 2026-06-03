/** Official State of Indiana / IDOI / Medicaid documents (opens in a new tab). */
const guides = [
  {
    title: 'Indiana Patient Bill of Rights',
    meta: 'PDF · Indiana.gov (SPD)',
    href: 'https://www.in.gov/spd/openenrollment/files/Rights-and-Protections-Against-Surprise-Medical-Bills.pdf',
  },
  {
    title: 'Claim Denial Checklist',
    meta: 'PDF · Indiana Medicaid',
    href: 'https://www.in.gov/medicaid/providers/files/modules/provider-and-member-utilization-review.pdf',
  },
  {
    title: 'IDOI Complaint Form Guide',
    meta: 'PDF · IDOI',
    href: 'https://www.in.gov/idoi/files/Consumer_Complaint_Form.pdf',
  },
  {
    title: 'Medicaid Appeals Handbook',
    meta: 'PDF · Indiana Medicaid',
    href: 'https://www.in.gov/medicaid/providers/files/modules/claim-administrative-review-and-appeals.pdf',
  },
]

/** Main Indiana Resources library (hub) — nested under IndianaResourcesLayout. */
export default function IndianaResourcesHub() {
  return (
    <div className="w-full">
      <header className="mb-12">
        <span className="inline-block px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest mb-4" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
          Regulatory Hub
        </span>
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4" style={{ color: 'var(--accent)', letterSpacing: '-0.03em' }}>Indiana Resources Hub</h1>
        <p className="text-lg leading-relaxed max-w-2xl" style={{ color: 'var(--ink-2)' }}>
          Navigate the complexities of Indiana insurance law with our curated library of statutes, consumer rights guides, and official regulatory portals.
        </p>
      </header>

      <div className="space-y-12">
        <section>
          <div className="flex items-center gap-3 mb-6">
            <span className="material-symbols-outlined" style={{ color: 'var(--accent)' }}>menu_book</span>
            <h2 className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>Educational Resources</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="col-span-1 md:col-span-2 p-8 rounded-2xl flex flex-col justify-between group hover:shadow-md transition-shadow" style={{ background: '#fff', border: '1px solid var(--line)', boxShadow: 'var(--sh-sm)' }}>
              <div>
                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--accent)' }}>Understanding ERISA in Indiana</h3>
                <p className="text-sm leading-relaxed mb-6" style={{ color: 'var(--ink-2)' }}>
                  The Employee Retirement Income Security Act (ERISA) governs most private-sector health plans. Learn how Indiana&apos;s &quot;Bad Faith&quot; laws interact with federal ERISA preemption during the appeal process.
                </p>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--accent)' }}>Deep Dive Analysis</span>
                <a href="https://www.erisaexperience.com/blog/self-funded-plans-vs-insured-plans-what-is-the-difference/" target="_blank" rel="noopener noreferrer" className="p-2 rounded-full transition-colors" style={{ background: 'var(--canvas)', color: 'var(--accent)' }}>
                  <span className="material-symbols-outlined">arrow_forward</span>
                </a>
              </div>
            </div>

            <div className="p-8 rounded-2xl flex flex-col justify-between" style={{ background: 'var(--accent)', color: '#fff' }}>
              <span className="material-symbols-outlined text-4xl opacity-50 mb-4">gavel</span>
              <div>
                <h3 className="text-lg font-bold mb-2">Indiana Code Title 27</h3>
                <p className="text-xs leading-relaxed" style={{ color: 'rgba(255,255,255,0.75)' }}>
                  Direct access to the Indiana Statutes regulating insurance companies, claim settlements, and unfair practices.
                </p>
              </div>
              <a
                href="https://iga.in.gov/laws/2024/ic/titles/27"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-6 text-sm font-bold underline underline-offset-4 hover:text-white transition-colors"
              >
                View Statutes
              </a>
            </div>

            <div className="p-8 rounded-2xl flex flex-col md:flex-row gap-6 items-center md:col-span-3" style={{ background: '#fff', border: '1px solid var(--line)' }}>
              <div>
                <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--accent)' }}>External Review (IDOI)</h3>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-2)' }}>
                  When an internal appeal fails, Indiana law allows for an External Review by an Independent Review Organization (IRO) through the Indiana Department of Insurance.
                </p>
                <div className="mt-4 flex flex-wrap gap-4 items-center">
                  <span className="px-2 py-1 rounded-full text-[10px] font-bold" style={{ background: '#fff3cd', color: '#7a5c00' }}>MANDATORY STEP</span>
                  <span className="px-2 py-1 rounded-full text-[10px] font-bold" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>IC 27-8-29</span>
                  <a href="https://www.in.gov/idoi/consumer-services/internal-and-external-grievance-procedures/" target="_blank" rel="noopener noreferrer" className="font-bold text-xs inline-flex items-center gap-1 hover:underline ml-auto" style={{ color: 'var(--accent)' }}>
                    IDOI Grievance Guide <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section>
          <div className="flex items-center gap-3 mb-6">
            <span className="material-symbols-outlined" style={{ color: 'var(--accent)' }}>download</span>
            <h2 className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>Consumer Guides</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {guides.map(({ title, meta, href }) => (
              <div key={title} className="p-6 rounded-2xl flex flex-col items-center text-center transition-all hover:shadow-md" style={{ background: '#fff', border: '1px solid var(--line)' }}>
                <span className="material-symbols-outlined text-4xl mb-4" style={{ color: 'var(--accent)' }}>picture_as_pdf</span>
                <h4 className="text-sm font-bold mb-1" style={{ color: 'var(--accent)' }}>{title}</h4>
                <p className="text-[10px] mb-4" style={{ color: 'var(--ink-3)' }}>{meta}</p>
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full py-2 text-xs font-bold rounded-full transition-colors text-center hover:opacity-80"
                  style={{ background: 'var(--accent)', color: '#fff' }}
                >
                  Download
                </a>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl p-8 relative overflow-hidden" style={{ background: '#fff', border: '1px solid var(--line)' }}>
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <span className="material-symbols-outlined text-9xl">support_agent</span>
          </div>
          <div className="relative z-10">
            <h2 className="text-2xl font-bold mb-6" style={{ color: 'var(--accent)' }}>External Assistance</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="flex gap-4">
                <div className="w-12 h-12 shrink-0 rounded-xl flex items-center justify-center text-white" style={{ background: 'var(--accent)' }}>
                  <span className="material-symbols-outlined">link</span>
                </div>
                <div>
                  <h4 className="font-bold mb-1" style={{ color: 'var(--accent)' }}>IDOI Complaint Portal</h4>
                  <p className="text-sm mb-3" style={{ color: 'var(--ink-2)' }}>The official Indiana Department of Insurance portal for filing formal complaints against insurance carriers.</p>
                  <a
                    href="https://www.in.gov/idoi/consumer-services/complaints/submit-a-complaint-online/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-bold text-xs inline-flex items-center gap-1 hover:underline"
                    style={{ color: 'var(--accent)' }}
                  >
                    VISIT IN.GOV <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="w-12 h-12 shrink-0 rounded-xl flex items-center justify-center text-white" style={{ background: 'var(--ink-2)' }}>
                  <span className="material-symbols-outlined">call</span>
                </div>
                <div>
                  <h4 className="font-bold mb-1" style={{ color: 'var(--accent)' }}>Consumer Assistance Hotline</h4>
                  <p className="text-sm mb-3" style={{ color: 'var(--ink-2)' }}>Speak with an IDOI representative for immediate guidance on Indiana insurance regulations.</p>
                  <a href="tel:+18006224461" className="font-bold text-xs inline-flex items-center gap-1 hover:underline" style={{ color: 'var(--accent)' }}>
                    1-800-622-4461 <span className="material-symbols-outlined text-sm">phone_forwarded</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="pt-12" style={{ borderTop: '1px solid var(--line)' }}>
          <div className="p-8 rounded-2xl" style={{ background: '#fff', borderLeft: '4px solid #dc2626' }}>
            <h3 className="text-sm font-bold uppercase tracking-widest mb-4" style={{ color: '#dc2626' }}>Legal Disclaimer &amp; Compliance</h3>
            <div className="space-y-4 text-xs leading-relaxed" style={{ color: 'var(--ink-2)' }}>
              <p>
                Resolvly is an independent advocacy tool and is not affiliated with, endorsed by, or partnered with the Indiana Department of Insurance (IDOI) or any federal health agency. The information provided in this Indiana Resources Hub is for educational purposes only and does not constitute legal advice.
              </p>
              <p>
                While we strive to maintain the most current information regarding the Indiana Code and ERISA regulations, statutes are subject to change by the Indiana General Assembly. Users should verify specific statutory language via the official Indiana General Assembly website (iga.in.gov).
              </p>
              <p>
                Use of Resolvly does not create an attorney-client relationship. If you require legal representation, we recommend contacting the Indiana State Bar Association&apos;s lawyer referral service.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
