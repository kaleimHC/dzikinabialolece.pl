import React from "react";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen bg-gray-900 text-white p-5 text-center">
          <h1 className="text-2xl mb-4">😢 Coś poszło nie tak</h1>
          <p className="mb-4">Aplikacja napotkała nieoczekiwany błąd.</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-green-600 rounded hover:bg-green-700"
          >
            Odśwież stronę
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
