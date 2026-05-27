import React from 'react';
import { render } from '@testing-library/react';
import UserProfile from './UserProfile';

test('renders user profile', () => {
  const { getByText } = render(<UserProfile />);
  expect(getByText(/John Doe/)).toBeInTheDocument();
  expect(getByText(/john@example.com/)).toBeInTheDocument();
});