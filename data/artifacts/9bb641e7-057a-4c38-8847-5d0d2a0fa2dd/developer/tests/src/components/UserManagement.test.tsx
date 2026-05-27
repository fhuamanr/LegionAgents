import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import UserManagement from './UserManagement';

test('handles login', () => {
  const handleLogin = jest.fn();
  const { getByText } = render(<UserManagement onLogin={handleLogin} />);

  fireEvent.click(getByText(/Login/i));
  expect(handleLogin).toHaveBeenCalled();
});