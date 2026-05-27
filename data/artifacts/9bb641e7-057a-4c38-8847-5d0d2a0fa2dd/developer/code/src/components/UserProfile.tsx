import React from 'react';

const UserProfile = () => {
  const user = { name: 'John Doe', email: 'john@example.com' };

  return (
    <div>
      <h2>{user.name}</h2>
      <p>{user.email}</p>
    </div>
  );
};

export default UserProfile;