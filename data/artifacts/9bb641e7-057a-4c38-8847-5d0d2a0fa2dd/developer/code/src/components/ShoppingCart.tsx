<div>
  <h1>Shopping Cart</h1>
  {cartItems.map((item) => (
    <div key={item.id}>{item.name}</div>
  ))}
</div>