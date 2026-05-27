<div>
  <h1>Product List</h1>
  <ul>
    {products.map(product => (
      <li key={product.id}>{product.name}</li>
    ))}
  </ul>
</div>