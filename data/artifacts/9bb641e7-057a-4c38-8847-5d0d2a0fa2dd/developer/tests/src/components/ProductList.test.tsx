import React from 'react';
import { render } from '@testing-library/react';
import ProductList from './ProductList';

test('renders products', () => {
  const products = [{ id: 1, name: 'Test Product' }];
  const { getByText } = render(<ProductList products={products} />);

  expect(getByText(/Test Product/i)).toBeInTheDocument();
});