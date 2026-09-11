function GeneralWrapperStyled({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`max-w-(--breakpoint-2xl) mx-auto px-4 sm:px-6 lg:px-8 py-5 tracking-tight relative ${className}`} style={{ zIndex: 'var(--z-content)' }}>
      {children}
    </div>
  )
}

export default GeneralWrapperStyled
