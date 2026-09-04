export async function resolve(specifier, context, defaultResolve) {
  if (specifier.endsWith('.css')) {
    return {
      url: new URL(specifier, context.parentURL).href,
      format: 'module',
      shortCircuit: true
    }
  }
  return defaultResolve(specifier, context, defaultResolve)
}

export async function load(url, context, defaultLoad) {
  if (url.endsWith('.css')) {
    return {
      format: 'module',
      source: 'export default {}',
      shortCircuit: true
    }
  }
  return defaultLoad(url, context, defaultLoad)
}
