export default function Footer({ disclaimer }: { disclaimer?: string }) {
  return (
    <footer className="mt-auto w-full border-t border-slate-200 bg-slate-100 py-6 dark:border-slate-700 dark:bg-slate-900/80">
      <div className="flex flex-col md:flex-row justify-between items-center px-8 gap-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 dark:text-slate-400">
          © 2024 Resolvly. Indiana Regulatory Compliant.
        </div>
        <div className="flex gap-6 text-[10px] uppercase tracking-widest">
          <a href="#" className="text-slate-500 opacity-80 transition-all hover:text-sky-800 hover:opacity-100 dark:text-slate-400 dark:hover:text-sky-300">IDOI Portal</a>
          <a href="#" className="text-slate-500 opacity-80 transition-all hover:text-sky-800 hover:opacity-100 dark:text-slate-400 dark:hover:text-sky-300">Privacy Policy</a>
          <a href="#" className="text-slate-500 opacity-80 transition-all hover:text-sky-800 hover:opacity-100 dark:text-slate-400 dark:hover:text-sky-300">Terms of Service</a>
          <a href="#" className="text-slate-500 opacity-80 transition-all hover:text-sky-800 hover:opacity-100 dark:text-slate-400 dark:hover:text-sky-300">Legal Disclaimer</a>
        </div>
      </div>
      {disclaimer && (
        <div className="mt-4 px-8 max-w-7xl mx-auto text-center">
          <p className="mx-auto max-w-3xl text-[9px] uppercase leading-relaxed tracking-widest text-slate-400 dark:text-slate-500">
            {disclaimer}
          </p>
        </div>
      )}
    </footer>
  )
}
