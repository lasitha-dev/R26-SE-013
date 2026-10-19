import React from 'react'

/**
 * Feature-level error boundary for the three Geospatial pages. Without it a
 * render error in one page unmounts the whole React root and the vet sees
 * a blank window (sidebar, header and tabs gone). With it the host shell and
 * the Geospatial tabs stay up and the page area explains what failed.
 *
 * `resetKey` (the current route) clears the error when the vet switches tab;
 * "Try again" re-mounts the page. The error text is shown as-is (no stack,
 * no data); nothing is retried automatically.
 */
export default class GeospatialRouteBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null, attempt: 0 }
    this.handleRetry = this.handleRetry.bind(this)
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Keep the real cause visible to developers in the browser console.
    console.error('[Geospatial] page render failed', error, info?.componentStack)
  }

  componentDidUpdate(prevProps) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) this.setState({ error: null })
  }

  handleRetry() {
    this.setState((prev) => ({ error: null, attempt: prev.attempt + 1 }))
  }

  render() {
    const { error, attempt } = this.state
    if (!error) return <React.Fragment key={attempt}>{this.props.children}</React.Fragment>
    return (
      <div className="rounded-xl border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-100" role="alert">
        <div className="font-semibold">This Geospatial page could not be displayed.</div>
        <div className="mt-1 text-xs text-red-200/90">
          {this.props.pageLabel ? `${this.props.pageLabel}: ` : ''}
          {String(error?.message || error)}
        </div>
        <div className="mt-1 text-xs text-red-200/70">Other ADRS sections and the other Geospatial tabs are still available.</div>
        <button
          type="button"
          onClick={this.handleRetry}
          className="mt-3 rounded border border-red-300/40 px-3 py-1 text-xs font-medium text-red-100 hover:bg-red-400/20"
        >
          Try again
        </button>
      </div>
    )
  }
}
