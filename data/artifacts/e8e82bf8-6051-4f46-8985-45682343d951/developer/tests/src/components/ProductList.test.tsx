import React from 'react';
import { render } from '@testing-library/react';
import ProductList from './ProductList';

test('renders product list', () => {
  const products = [{ id: 1, name: 'Product 1' }, { id: 2, name: 'Product 2' }];
  const { getByText } = render(<ProductList products={products} />);

  expect(getByText('Product 1')).toBeInTheDocument();
  expect(getByText('Product 2')).toBeInTheDocument();
});