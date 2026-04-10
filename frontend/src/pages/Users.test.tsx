import { useEffect, useState } from 'react';

const Users: React.FC = () => {
  console.log('[Users-Test] Component mounted');
  const [loaded, setLoaded] = useState(false);
  
  useEffect(() => {
    console.log('[Users-Test] useEffect triggered');
    setLoaded(true);
  }, []);

  return (
    <div style={{ padding: 24 }}>
      <h1>Users Test Page</h1>
      <p>Component loaded: {loaded ? 'Yes' : 'No'}</p>
      <p>If you see this, the component is working!</p>
    </div>
  );
};

export default Users;
