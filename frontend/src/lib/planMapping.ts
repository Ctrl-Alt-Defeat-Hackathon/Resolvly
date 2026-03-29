/** Map AnalyzeFlow UI state to backend PlanContext and wizard request bodies. */

export function buildPlanContext(planType: string, funding: string): {
  plan_type: string
  regulation_type: string
  state: string
} {
  const state = 'IN'
  if (planType === 'employer') {
    if (funding === 'erisa') {
      return { plan_type: 'employer_erisa', regulation_type: 'erisa', state }
    }
    if (funding === 'insured') {
      return { plan_type: 'employer_fully_insured', regulation_type: 'state', state }
    }
    return { plan_type: 'employer_unknown', regulation_type: 'unknown', state }
  }
  if (planType === 'medicaid') {
    return { plan_type: 'medicaid', regulation_type: 'medicaid', state }
  }
  return { plan_type: 'individual', regulation_type: 'state', state }
}

export type WizardBody =
  | { source: 'employer'; employer_plan_type: 'erisa' | 'fully_insured' | 'unknown'; state: string }
  | { source: 'medicaid'; state: string }
  | { source: 'individual'; state: string }

export function buildWizardBody(planType: string, funding: string): WizardBody {
  const state = 'IN'
  if (planType === 'employer') {
    let employer_plan_type: 'erisa' | 'fully_insured' | 'unknown' = 'unknown'
    if (funding === 'erisa') employer_plan_type = 'erisa'
    else if (funding === 'insured') employer_plan_type = 'fully_insured'
    return { source: 'employer', employer_plan_type, state }
  }
  if (planType === 'medicaid') {
    return { source: 'medicaid', state }
  }
  return { source: 'individual', state }
}

export function canSubmitPlan(planType: string, funding: string): boolean {
  if (!planType) return false
  if (planType === 'employer' && !funding) return false
  return true
}
