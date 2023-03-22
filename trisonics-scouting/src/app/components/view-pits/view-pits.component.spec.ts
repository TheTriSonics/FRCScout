import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ViewPitsComponent } from './view-pits.component';

describe('ViewPitsComponent', () => {
  let component: ViewPitsComponent;
  let fixture: ComponentFixture<ViewPitsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ViewPitsComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ViewPitsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
