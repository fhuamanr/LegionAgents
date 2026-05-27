<div>
  <h1>Products</h1>
  {products.map((product) => (
    <div key={product.id}>{product.name}</div>
  ))}
</div>