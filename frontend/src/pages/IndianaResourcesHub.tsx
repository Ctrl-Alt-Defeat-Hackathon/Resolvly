const guides = [
  { title: 'Indiana Patient Bill of Rights', size: 'PDF • 1.2 MB' },
  { title: 'Claim Denial Checklist', size: 'PDF • 840 KB' },
  { title: 'IDOI Complaint Form Guide', size: 'PDF • 2.1 MB' },
  { title: 'Medicaid Appeals Handbook', size: 'PDF • 3.5 MB' },
]

/** Main Indiana Resources library (hub) — nested under IndianaResourcesLayout. */
export default function IndianaResourcesHub() {
  return (
    <div className="max-w-6xl mx-auto bg-surface">
      <header className="mb-12">
        <div className="inline-block px-3 py-1 bg-secondary-container text-on-secondary-container rounded-full text-[10px] font-bold uppercase tracking-widest mb-4">
          Regulatory Hub
        </div>
        <h1 className="text-4xl md:text-5xl font-extrabold text-primary tracking-tight font-headline mb-4">Indiana Resources Hub</h1>
        <p className="text-lg text-on-surface-variant leading-relaxed max-w-2xl">
          Navigate the complexities of Indiana insurance law with our curated library of statutes, consumer rights guides, and official regulatory portals.
        </p>
      </header>

      <div className="space-y-12">
        <section>
          <div className="flex items-center gap-3 mb-6">
            <span className="material-symbols-outlined text-primary-container">menu_book</span>
            <h2 className="text-2xl font-bold text-primary">Educational Resources</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="col-span-1 md:col-span-2 bg-surface-container-lowest p-8 rounded-xl shadow-sm border border-outline-variant/10 flex flex-col justify-between group hover:shadow-md transition-shadow">
              <div>
                <h3 className="text-xl font-bold text-primary mb-3">Understanding ERISA in Indiana</h3>
                <p className="text-sm text-on-surface-variant leading-relaxed mb-6">
                  The Employee Retirement Income Security Act (ERISA) governs most private-sector health plans. Learn how Indiana&apos;s &quot;Bad Faith&quot; laws interact with federal ERISA preemption during the appeal process.
                </p>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-primary uppercase tracking-wider">Deep Dive Analysis</span>
                <button type="button" className="p-2 rounded-full bg-surface-container hover:bg-primary hover:text-on-primary transition-colors">
                  <span className="material-symbols-outlined">arrow_forward</span>
                </button>
              </div>
            </div>

            <div className="bg-primary-container p-8 rounded-xl text-on-primary flex flex-col justify-between">
              <span className="material-symbols-outlined text-4xl opacity-50 mb-4">gavel</span>
              <div>
                <h3 className="text-lg font-bold mb-2">Indiana Code Title 27</h3>
                <p className="text-xs text-on-primary-container leading-relaxed">
                  Direct access to the Indiana Statutes regulating insurance companies, claim settlements, and unfair practices.
                </p>
              </div>
              <a href="#" className="mt-6 text-sm font-bold underline underline-offset-4 hover:text-white transition-colors">View Statutes</a>
            </div>

            <div className="bg-surface-container-low p-8 rounded-xl flex flex-col md:flex-row gap-6 items-center md:col-span-3 border border-outline-variant/10">
              <img
                alt="Indiana Department of Insurance Building"
                className="w-full md:w-48 h-32 object-cover rounded-lg"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDcrivu7BbiBWtQRbB_o357ht7SMv2cGuxyJ9X1WW4-L_0t9GRNjJ_A1L4kXWfnV56hZsfFQ3ka0OfV-b747RbDjIjryWydoPYWSyiof6psJeNDml56UiARP_HYgHKIl9G3sJcyG7_CyIdld8BGaUcUhVAypYLiWI40ADgW310pB3FmE08rntRuFByN4BKVhY3mQEUzCjfM7WxerGFPmYsDPetll4gSDlsaOwX80DJFQ3l7Val0WTyrcg_KATdSeDmxZOGz3A4P140"
              />
              <div>
                <h3 className="text-lg font-bold text-primary mb-2">External Review (IDOI)</h3>
                <p className="text-sm text-on-surface-variant leading-relaxed">
                  When an internal appeal fails, Indiana law allows for an External Review by an Independent Review Organization (IRO) through the Indiana Department of Insurance.
                </p>
                <div className="mt-4 flex gap-4">
                  <span className="px-2 py-1 bg-tertiary-fixed text-on-tertiary-fixed text-[10px] font-bold rounded">MANDATORY STEP</span>
                  <span className="px-2 py-1 bg-secondary-fixed text-on-secondary-fixed text-[10px] font-bold rounded">IC 27-8-29</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section>
          <div className="flex items-center gap-3 mb-6">
            <span className="material-symbols-outlined text-primary-container">download</span>
            <h2 className="text-2xl font-bold text-primary">Consumer Guides</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {guides.map(({ title, size }) => (
              <div key={title} className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/20 hover:border-primary/30 transition-all flex flex-col items-center text-center">
                <span className="material-symbols-outlined text-primary text-4xl mb-4">picture_as_pdf</span>
                <h4 className="text-sm font-bold text-primary mb-1">{title}</h4>
                <p className="text-[10px] text-on-surface-variant mb-4">{size}</p>
                <button type="button" className="w-full py-2 bg-surface-container-high text-primary text-xs font-bold rounded-lg hover:bg-primary hover:text-on-primary transition-colors">
                  Download
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-surface-container-low rounded-2xl p-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10">
            <span className="material-symbols-outlined text-9xl">support_agent</span>
          </div>
          <div className="relative z-10">
            <h2 className="text-2xl font-bold text-primary mb-6">External Assistance</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="flex gap-4">
                <div className="w-12 h-12 shrink-0 bg-primary rounded-xl flex items-center justify-center text-white">
                  <span className="material-symbols-outlined">link</span>
                </div>
                <div>
                  <h4 className="font-bold text-primary mb-1">IDOI Complaint Portal</h4>
                  <p className="text-sm text-on-surface-variant mb-3">The official Indiana Department of Insurance portal for filing formal complaints against insurance carriers.</p>
                  <a href="#" className="text-primary font-bold text-xs inline-flex items-center gap-1 hover:underline">
                    VISIT IN.GOV <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="w-12 h-12 shrink-0 bg-secondary rounded-xl flex items-center justify-center text-white">
                  <span className="material-symbols-outlined">call</span>
                </div>
                <div>
                  <h4 className="font-bold text-primary mb-1">Consumer Assistance Hotline</h4>
                  <p className="text-sm text-on-surface-variant mb-3">Speak with an IDOI representative for immediate guidance on Indiana insurance regulations.</p>
                  <a href="#" className="text-primary font-bold text-xs inline-flex items-center gap-1 hover:underline">
                    1-800-622-4461 <span className="material-symbols-outlined text-sm">phone_forwarded</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-t border-outline-variant/30 pt-12">
          <div className="bg-surface-container-lowest p-8 rounded-xl border-l-4 border-error">
            <h3 className="text-sm font-bold text-error uppercase tracking-widest mb-4">Legal Disclaimer &amp; Compliance</h3>
            <div className="space-y-4 text-xs text-on-surface-variant leading-relaxed">
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
