import React, { useState, useEffect } from 'react';
import { Text } from 'react-native';

function formatRelative(timestamp) {
  if (!timestamp) return 'Never';
  const date = new Date(timestamp);
  const now = new Date();
  const diffSec = Math.floor((now - date) / 1000);

  if (diffSec < 60) return 'Just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  return `${diffDays}d ago`;
}

export const RelativeTime = React.memo(function RelativeTime({ timestamp, style, prefix = '', suffix = '' }) {
  const [relTime, setRelTime] = useState(() => formatRelative(timestamp));

  useEffect(() => {
    setRelTime(formatRelative(timestamp));
    const interval = setInterval(() => {
      setRelTime(formatRelative(timestamp));
    }, 60000); // Ticks every 60 seconds locally without re-rendering parent tree
    return () => clearInterval(interval);
  }, [timestamp]);

  return <Text style={style}>{prefix}{relTime}{suffix}</Text>;
});
