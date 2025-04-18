import { useEffect, useRef } from 'react';

// Simple polling hook
// callback: function to call on each interval
// interval: time in ms between calls (null to disable)
function usePolling(callback: () => Promise<void>, interval: number | null) {
  const savedCallback = useRef<(() => Promise<void>) | null>(null);

  // Remember the latest callback.
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Set up the interval.
  useEffect(() => {
    function tick() {
      savedCallback.current?.();
    }
    if (interval !== null) {
      const id = setInterval(tick, interval);
      // Initial call
      tick();
      return () => clearInterval(id);
    }
  }, [interval]);
}

export default usePolling; 