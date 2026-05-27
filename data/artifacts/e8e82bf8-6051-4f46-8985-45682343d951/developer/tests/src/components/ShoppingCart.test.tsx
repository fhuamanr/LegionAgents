import React from 'react';
import { render } from '@testing-library/react';
import ShoppingCart from './ShoppingCart';

test('renders shopping cart items', () => {
  const cartItems = [{ id: 1, name: 'Item 1', price: 10 }, { id: 2, name: 'Item 2', price: 20 }];
  const { getByText } = render(<ShoppingCart cartItems={cartItems} />);

  expect(getByText('Item 1 - $10')).toBeInTheDocument();
  expect(getByText('Item 2 - $20')).toBeInTheDocument();
});