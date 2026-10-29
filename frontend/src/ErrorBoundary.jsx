import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    console.error("Unexpected UI error", error);
  }

  render() {
    if (this.state.hasError) {
      return <main className="app-error" role="alert"><h1>Something went wrong</h1><p>Please refresh the page and try again.</p></main>;
    }
    return this.props.children;
  }
}
