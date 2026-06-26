export function splitBehaviorRules(input: string): string[] {
  return input
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

export function joinBehaviorRules(rules: string[]): string {
  return rules.join('\n')
}
