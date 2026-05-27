import React from 'react';
import { render } from '@testing-library/react';
import ShoppingCart from './ShoppingCart';

test('renders cart items', () => {
  const cartItems = [{ id: 1, name: 'Test Item' }];
  const { getByText } = render(<ShoppingCart cartItems={cartItems} />);

  expect(getByText(/Test Item/i)).toBeInTheDocument();
});