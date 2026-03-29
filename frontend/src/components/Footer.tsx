export default function Footer({ disclaimer }: { disclaimer?: string }) {
  return (
    <footer className="w-full py-6 mt-auto bg-slate-100 border-t border-slate-200">
      <div className="flex flex-col md:flex-row justify-between items-center px-8 gap-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500">
          © 2024 Resolvly. Indiana Regulatory Compliant.
        </div>
        <div className="flex gap-6 text-[10px] uppercase tracking-widest">
          <a href="#" className="text-slate-500 hover:text-sky-800 transition-all opacity-80 hover:opacity-100">IDOI Portal</a>
          <a href="#" className="text-slate-500 hover:text-sky-800 transition-all opacity-80 hover:opacity-100">Privacy Policy</a>
          <a href="#" className="text-slate-500 hover:text-sky-800 transition-all opacity-80 hover:opacity-100">Terms of Service</a>
          <a href="#" className="text-slate-500 hover:text-sky-800 transition-all opacity-80 hover:opacity-100">Legal Disclaimer</a>
        </div>
      </div>
      {disclaimer && (
        <div className="mt-4 px-8 max-w-7xl mx-auto text-center">
          <p className="text-[9px] text-slate-400 leading-relaxed uppercase tracking-widest max-w-3xl mx-auto">
            {disclaimer}
          </p>
        </div>
      )}
    </footer>
  )
}
